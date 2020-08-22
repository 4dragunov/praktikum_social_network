from django.shortcuts import render, get_object_or_404
from django.shortcuts import redirect, Http404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page

from django.core.paginator import Paginator
from .forms import PostForm, CommentForm
from .models import Post, Group, Comment, Follow

User = get_user_model()


def index(request):
    post_list = Post.objects.select_related('author').all()
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)
    return render(
        request,
        'index.html',
        {'page': page, 'paginator': paginator}
    )


def group_posts(request, slug):
    group = get_object_or_404(Group, slug=slug)
    post_list = Post.objects.filter(group=group).all()
    paginator = Paginator(post_list, 3)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)
    return render(request,
                  "group.html",
                  {"group": group, 'page': page, 'paginator': paginator, })


@login_required
def new_post(request):
    form = PostForm(request.POST or None, files=request.FILES or None)
    if form.is_valid():
        form.instance.author = request.user
        form.save()
        return redirect('index')
    return render(request, 'new_post.html', {'form': form})


def profile(request, username):
    author = get_object_or_404(User, username=username)
    user = request.user
    paginator = Paginator(author.posts.all(), 10)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)

    return render(request, 'profile.html',
                  context={'page': page,
                           'paginator': paginator,
                           'author': author,
                           'user': user,

                           })


def post_view(request, username, post_id):
    post = get_object_or_404(Post, pk=post_id)
    author = get_object_or_404(User, username=username)

    # Здесь тоже можно было бы обойтись related_name
    # {% for item in post.comments.all %}
    # но  pytest требует отправку QuerySet
    items = Comment.objects.filter(post__id=post_id)

    form = CommentForm()

    return render(request, 'post.html', {'author': author,
                                         'post': post,
                                         'form': form,
                                         'items': items,
                                         })


@login_required
def post_edit(request, username, post_id):
    is_form_edit = True
    post = get_object_or_404(Post, author__username=username,
                             pk__iexact=post_id)
    if post.author == request.user:
        form = PostForm(request.POST or None,
                        files=request.FILES or None, instance=post)
        if form.is_valid():
            post = form.save()
            return redirect('post', username, post_id)
        form = PostForm(instance=post)

        return render(request, "new_post.html",
                      context={'form': form,
                               "is_form_edit": is_form_edit,
                               'post': post})
    else:
        return redirect('index')


def page_not_found(request, exception):
    return render(
        request,
        "misc/404.html",
        {"path": request.path},
        status=404
    )


def server_error(request):
    return render(request, "misc/500.html", status=500)


@login_required
def add_comment(request, username, post_id):
    post = get_object_or_404(Post,
                             author__username=username,
                             pk__iexact=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        new_comment = form.save(commit=False)
        form.instance.author = request.user
        form.instance.post = post
        new_comment.save()
        return redirect('post', username, post_id)
    return render(request, "post.html", context={"form": form})


@login_required
def follow_index(request):
    post_list = Post.objects.filter(author__following__user=request.user)
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)
    return render(
        request,
        "follow.html",
        {'page': page, 'paginator': paginator}
    )


@login_required
def profile_follow(request, username):
    author = get_object_or_404(User, username=username)
    if author != request.user:
        Follow.objects.get_or_create(user=request.user, author=author)
    return redirect('profile', username=username)


@login_required
def profile_unfollow(request, username):
    author = get_object_or_404(User, username=username)
    profile_follow = get_object_or_404(Follow, author=author)
    profile_follow.delete()
    return redirect('profile', username=username)
