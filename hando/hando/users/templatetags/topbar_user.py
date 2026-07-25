from django import template

register = template.Library()


@register.simple_tag
def topbar_display_name(user):
    if not getattr(user, "is_authenticated", False):
        return ""

    profile = getattr(user, "profile", None)
    profile_name = getattr(profile, "full_name", "")
    if profile_name and profile_name.strip():
        return profile_name.strip()

    full_name = user.get_full_name()
    if full_name and full_name.strip():
        return full_name.strip()

    email = getattr(user, "email", "")
    if email and email.strip():
        return email.strip()

    return "Usuário"


@register.simple_tag
def topbar_avatar_url(user):
    if not getattr(user, "is_authenticated", False):
        return ""

    profile = getattr(user, "profile", None)
    avatar = getattr(profile, "avatar", None)
    if not avatar:
        return ""

    try:
        if avatar.name and avatar.storage.exists(avatar.name):
            return avatar.url
    except (OSError, ValueError):
        return ""

    return ""
