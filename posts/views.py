from django.shortcuts import render, get_object_or_404
from django.shortcuts import redirect, Http404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

from django.core.paginator import Paginator
from .forms import PostForm, CommentForm
from .models import Post, Group, Comment, Follow

User = get_user_model()


def index(request):
    post_list = Post.objects.order_by('-pub_date').all()
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
    if request.method == 'POST':
        form = PostForm(request.POST, files=request.FILES or None)
        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.author = request.user
            new_post.save()
            return redirect("index")

    form = PostForm()
    return render(request, "new_post.html", context={"form": form})


def profile(request, username):
    is_user_author = False
    if not User.objects.filter(username=username).exists():
        raise Http404("К сожалению запрашиваемый пользователь/"
                      " еще не зарегистрирован")
    author = User.objects.get(username=username)
    profile = User.objects.get(username=username)

    if str(author) == str(request.user):
        is_user_author = True

    profile_posts = Post.objects.filter(author=author)
    followers_count = Follow.objects.filter(author=author).count()
    following_count = Follow.objects.filter(user=author).count()

    total_posts = Post.objects.filter(author__username=username).count()

    paginator = Paginator(profile_posts, 10)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)
    following = (Follow.objects.filter(user__username=request.user).
                 filter(author=author).count())

    return render(request, 'profile.html',
                  context={'page': page,
                           'paginator': paginator,
                           'total_posts': total_posts,
                           'author': author,
                           'profile_posts': profile_posts,
                           'is_user_author': is_user_author,
                           'profile': profile,
                           'following': following,
                           'followers_count': followers_count,
                           'following_count': following_count
                           })


def post_view(request, username, post_id):
    post = get_object_or_404(Post, pk=post_id)
    is_user_author = False
    post_author = User.objects.get(username=username)
    post_count = Post.objects.filter(author__username=post_author).count()
    print(post_count)

    items = Comment.objects.filter(post__id=post_id)

    folowers = Follow.objects.filter(author=post_author).count()
    following = Follow.objects.filter(user=post_author).count()

    if request.user == post_author:
        is_user_author = True

    form = CommentForm()

    return render(request, 'post.html', {'post_author': post_author,
                                         'post': post,
                                         'is_user_author': is_user_author,
                                         'post_count': post_count,
                                         'form': form,
                                         'items': items,
                                         'folowers': folowers,
                                         'following': following
                                         })


@login_required
def post_edit(request, username, post_id):
    is_form_edit = True
    post = get_object_or_404(Post, author__username=username,
                             pk__iexact=post_id)
    if post.author == request.user:
        bound_form = PostForm(request.POST or None,
                              files=request.FILES or None, instance=post)
        if bound_form.is_valid():
            post = bound_form.save()
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

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            new_comment = form.save(commit=False)
            new_comment.author = request.user
            new_comment.post = post
            new_comment.save()
            return redirect('post', username, post_id)

    form = CommentForm()
    return render(request, "post.html", context={"form": form})


@login_required
def follow_index(request):
    follow_author = (User.objects.filter(following__user=request.user).
                     values('username'))
    print(follow_author)
    post_list = (Post.objects.filter(author__username__in=follow_author).
                 order_by('-pub_date').all())
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
    user = User.objects.get(username=username)
    if not Follow.objects.filter(user=request.user, author=user).exists():
        if user != request.user:
            Follow.objects.create(user=request.user, author=user)
    return redirect('profile', username=username)


@login_required
def profile_unfollow(request, username):
    user = User.objects.get(username=username)
    Follow.objects.get(user=request.user, author=user).delete()
    return redirect('profile', username=username)
