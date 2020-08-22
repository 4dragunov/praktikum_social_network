import time
from django.conf import settings

from django.test import TestCase, Client
from django.shortcuts import reverse
from django.contrib.auth.models import User
from django.test import override_settings
from django.core.cache import cache
from .models import Post, Group
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile


def get_test_image_file():
    from PIL import Image

    img = Image.new('RGB', (60, 30), color=(73, 109, 137))
    img.save('test.jpg')


@override_settings(CACHES=settings.TEST_CACHES)
class ProfileTest(TestCase):
    def check_post_in_page(self, url, text, user, group):
        response = self.client_auth.get(url)
        paginator = response.context.get('paginator')
        if paginator is not None:
            self.assertEqual(paginator.count, 1)
            post = response.context['page'][0]
        else:
            post = response.context['post']
        self.assertEqual(post.text, text)
        self.assertEqual(post.author, user)
        self.assertEqual(post.group, group)

    def setUp(self):
        self.client_auth = Client()
        self.user = User.objects.create_user(username="sarah")
        self.client_auth.force_login(self.user)

        self.client_unauth = Client()

    # После регистрации пользователя создается
    # его персональная страница (profile)
    def test_creation_profile_page_after_reg(self):
        response = self.client_auth.get(reverse('profile', args=(self.user,)))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["author"], User)
        self.assertEqual(response.context["author"].
                         username, self.user.username)

    # Авторизованный пользователь может опубликовать пост (new)
    def test_auth_user_can_publish_post(self):
        self.group = Group.objects.create(title="test", slug="test")

        self.post = Post.objects.create(
            text='Test text',
            author=self.user,
            group=self.group
        )
        new_post = self.client_auth.get(reverse('post',
                                                args=(self.user.username,
                                                      self.post.pk)))
        self.assertEqual(new_post.status_code, 200)

    # Неавторизованный посетитель не может опубликовать пост
    # (его редиректит на страницу входа)
    def test_unauth_user_cant_publish_post(self):
        new_post_page = self.client_unauth.get(reverse('new_post'))
        self.assertEqual(new_post_page.status_code, 302)
        self.assertRedirects(new_post_page,
                             "/auth/login/?next=/new/",
                             status_code=302,
                             target_status_code=200,
                             msg_prefix='')

    # После публикации поста новая запись появляется на главной
    # странице сайта (index), на персональной странице пользователя (profile),
    # и на отдельной странице поста (post)
    def test_post_appears_on_pages(self):

        self.group = Group.objects.create(title="test", slug="test")

        self.post = Post.objects.create(
            text='Test text',
            author=self.user,
            group=self.group
        )

        urls = (reverse('index'),
                reverse('profile', args=(self.user.username,)),
                reverse('post', args=(self.user.username, self.post.id,)),
                )

        for url in urls:
            with self.subTest(url=url):
                self.check_post_in_page(url, 'Test text', self.user,
                                        self.group)

    # Авторизованный пользователь может отредактировать свой пост
    # и его содержимое изменится на всех связанных страницах
    def test_auth_user_can_edit_post_appears_on_pages(self):

        self.group = Group.objects.create(title="test", slug="test")

        self.post = Post.objects.create(
            text="simple text",
            author=self.user,
            group=self.group,
        )

        self.client_auth.post(reverse('post_edit',
                                      args=(self.user, self.post.id,)),
                              data={'text': 'Test text',
                                    'author': self.user.username,
                                    'group': self.group.id, })

        urls = (reverse('index'),
                reverse('profile', args=(self.user.username,)),
                reverse('post', args=(self.user.username, self.post.id,)),
                reverse('group', args=(self.group.slug,)),
                )

        for url in urls:
            with self.subTest(url=url):
                self.check_post_in_page(url,
                                        'Test text',
                                        self.user,
                                        self.group)


@override_settings(CACHES=settings.TEST_CACHES)
class ImageTest(TestCase):

    def setUp(self):
        get_test_image_file()
        self.client = Client()
        self.user = User.objects.create_user(username="sarah")
        self.client.force_login(self.user)

        self.group = Group.objects.create(title="test",
                                          slug="test123",
                                          description='test')

        self.post_valid_file_type = Post.objects.create(
            text='Test text',
            author=self.user,
            group=self.group,
            image=SimpleUploadedFile(name='test.png',
                                     content=open('test.png', 'rb').read(),
                                     content_type='image/png'),
            pub_date=timezone.now()

        )

        self.post_invalid_file_type = Post.objects.create(
            text='Test text',
            author=self.user,
            group=self.group,
            pub_date=timezone.now()

        )

    def test_display_image_on_post_page(self):
        urls = (reverse('post', args=(self.user.username,
                                      self.post_valid_file_type.pk,)),
                reverse('profile', args=(self.user,)),
                reverse('index'),
                reverse('group', kwargs={'slug': self.group.slug}),
                )

        for url in urls:
            with self.subTest(url=url):
                url_page = self.client.get(url)
                self.assertIn("<img", url_page.content.decode())

    def test_upload_wrong_format_file(self):
        file = tempfile.NamedTemporaryFile(mode='w+t',
                                           suffix=".txt",
                                           delete=False)
        file.writelines(['Python\n'])
        file.seek(0)

        with file as img:
            response_txt = self.client.post(
                reverse('new_post'),
                {'text': 'post with wrong format file',
                 'author': self.user.username,
                 'image': img}, follow=True)

            error_text = (
                'Загрузите правильное изображение. Файл, который вы загрузили,'
                ' поврежден или не является изображением.')
            self.assertFormError(response_txt, 'form', 'image', error_text)


class CasheTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="sarah")
        self.client.force_login(self.user)

    def test_cache_timeout(self):
        self.group = Group.objects.create(title="test", slug="test")
        self.post1 = Post.objects.create(
            text='post1',
            author=self.user,
            group=self.group,
            image=SimpleUploadedFile(name='test.png',
                                     content=open('test.png', 'rb').read(),
                                     content_type='image/png'),
            pub_date=timezone.now()

        )

        response_index_1 = self.client.get(reverse('index'))
        self.assertContains(response_index_1, 'post1')

        self.post2 = Post.objects.create(
            text='simple text2',
            author=self.user,
            group=self.group
        )
        response_index_2 = self.client.get(reverse('index'))
        self.assertNotContains(response_index_2, 'simple text2')
        cache.clear()
        response_index_3 = self.client.get(reverse('index'))
        self.assertContains(response_index_3, 'simple text2')


@override_settings(CACHES=settings.TEST_CACHES)
class CommentTest(TestCase):
    def setUp(self):
        self.client_auth = Client()
        self.user1 = User.objects.create_user(username="sarah")
        self.user2 = User.objects.create_user(username="james")
        self.client_auth.force_login(self.user1)

        self.client_unauth = Client()

    def test_auth_user_can_subscribe_and_unsubscribe(self):
        response_get_profile = self.client_auth.get(
            reverse('profile', args=(self.user2,)))
        self.assertIn("Подписаться", response_get_profile.content.decode())
        self.assertNotIn("Отписаться", response_get_profile.content.decode())

        response_subscribe = self.client_auth.post(reverse('profile_follow',
                                                           args=(self.user2,)),
                                                   follow=True)
        self.assertIn("Отписаться", response_subscribe.content.decode())

        response_unsubscribe = self.client_auth.post(
            reverse('profile_unfollow',
                    args=(self.user2,)), follow=True)
        self.assertIn("Подписаться", response_unsubscribe.content.decode())

        response_subscribe_self_profile = self.client_auth.get(
            reverse('profile_follow', args=(self.user1,)))
        self.assertNotIn("Подписаться",
                         response_subscribe_self_profile.content.decode())
        self.assertNotIn("Отписаться",
                         response_subscribe_self_profile.content.decode())

    def test_only_auth_user_can_comment_post(self):
        self.post = Post.objects.create(
            text='simple text',
            author=self.user1
        )

        self.client_auth.post(reverse('add_comment',
                                      args=(self.user1, self.post.pk)),
                              {'text': 'test_text'})
        response_get_post_with_comment = self.client_auth.get(
            reverse('post', args=(self.user1, self.post.pk)))
        self.assertIn('test_text',
                      response_get_post_with_comment.content.decode())

        res_unauth_post_comment = \
            self.client_unauth.post(reverse('add_comment',
                                            args=(self.user1, self.post.pk)),
                                    {'text': 'test_text'})
        self.assertRedirects(res_unauth_post_comment,
                             "/auth/login/?next=/sarah/1/comment/",
                             status_code=302,
                             target_status_code=200,
                             msg_prefix='')

    def test_new_post_appears_in_follow_index(self):
        self.user3 = User.objects.create_user(username="Misha")

        self.post_user2 = Post.objects.create(
            text='simple text post favorite author',
            author=self.user2
        )

        self.post_user3 = Post.objects.create(
            text='simple text post',
            author=self.user3
        )

        self.client_auth.post(reverse('profile_follow',
                                      args=(self.user2,)), follow=True)

        resp_follow_index = self.client_auth.get(reverse('follow_index'))
        self.assertIn("simple text post favorite author",
                      resp_follow_index.content.decode())
        self.assertNotIn("simple text post3",
                         resp_follow_index.content.decode())