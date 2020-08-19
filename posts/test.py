import time
from django.test import TestCase, Client
from django.shortcuts import reverse
from django.contrib.auth.models import User
from .models import Post, Group
from django.utils import timezone


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
        new_post = self.client_auth.get(reverse('new_post'))
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
            self.check_post_in_page(url, 'Test text', self.user, self.group)

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
            self.check_post_in_page(url, 'Test text', self.user, self.group)


class ImageTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="sarah")
        self.client.force_login(self.user)

        self.group = Group.objects.create(title="test",
                                          slug="test123",
                                          description='test')

        self.post = Post.objects.create(
            text='Test text',
            author=self.user,
            group=self.group,
            pub_date=timezone.now()

        )

    def test_display_image_on_post_page(self):
        with open('posts/media/file.jpeg', 'rb') as img:
            self.client.post(reverse('post_edit',
                                     kwargs={'username': self.user.username,
                                             'post_id': self.post.pk}),
                             {'text': 'post with image post',
                              'author': self.user.username,
                              'group': self.group.id,
                              'image': img},
                             follow=True)

        urls = (reverse('post', args=(self.user.username, self.post.pk,)),
                reverse('profile', args=(self.user,)),
                reverse('index'),
                reverse('group', kwargs={'slug': self.group.slug}),
                )

        for url in urls:
            url_page = self.client.get(url)
            self.assertIn("<img", url_page.content.decode())

    def test_upload_wrong_format_file(self):
        with open('posts/media/file.txt', 'rb') as img:
            responce = self.client.post(
                reverse('post_edit',
                        kwargs={'username': self.user.username,
                                'post_id': self.post.pk}),
                {'text': 'post with wrong format file',
                 'author': self.user.username,
                 'group': self.group.id,
                 'image': img})
            self.assertEqual(responce.status_code, 200)
            post_responce = self.client.get(reverse('index'))
            self.assertNotContains(post_responce,
                                   'post with wrong format file')
            self.assertContains(post_responce, 'post1')


class CasheTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="sarah")
        self.client.force_login(self.user)

    def test_cache_timeout(self):
        self.group = Group.objects.create(title="test", slug="test")
        self.post1 = Post.objects.create(
            text='simple text',
            author=self.user,
            group=self.group
        )
        with open('posts/media/file.jpeg', 'rb') as img:
            self.client.post(reverse('post_edit', kwargs={
                                         'username': self.user.username,
                                         'post_id': self.post1.pk}),
                             {'text': 'post1',
                              'author': self.user.username,
                              'group': self.group.id,
                              'image': img},
                             follow=True)

        response_index_1 = self.client.get(reverse('index'))
        self.assertContains(response_index_1, 'post1')

        self.post2 = Post.objects.create(
            text='simple text2',
            author=self.user,
            group=self.group
        )
        response_index_2 = self.client.get(reverse('index'))
        self.assertNotContains(response_index_2, 'simple text2')
        time.sleep(21)
        response_index_3 = self.client.get(reverse('index'))
        self.assertContains(response_index_3, 'simple text2')
