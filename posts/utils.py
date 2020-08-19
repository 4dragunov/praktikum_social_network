def user_only(func):
    def check_user(request, *args, **kwargs):
        if not request.user.is_authenticated():
            return response.redirect(
                to_page='/auth/login',
                params={'next': current_page}
            )
        func(request, *args, **kwargs)

    return check_user
