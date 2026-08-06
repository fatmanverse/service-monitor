"""Service visibility rules shared by the REST routers.

A service reaches a non-admin user through either of two independent grants:

* its resource group is granted to the user in `user_resource_groups`, or
* the service itself is granted to the user in `user_services`.

The second path is what makes a service without a resource group reachable at
all, but it is deliberately not restricted to those: granting a single service
out of an otherwise ungranted group is a legitimate, narrower permission than
granting the whole group.
"""

from sqlalchemy import ColumnElement, or_, select

from .models import Service, User, UserResourceGroup, UserService


def service_visibility_filter(user: User) -> ColumnElement[bool]:
    """Builds the predicate restricting `Service` rows to what `user` may see.

    Both grants are expressed as `IN (subquery)` rather than joins so that
    callers keep one row per service. A join would multiply rows for a service
    reachable through several grants, which breaks `Session.scalar` and forces
    every list caller to deduplicate.
    """
    granted_groups = select(UserResourceGroup.resource_group_id).where(
        UserResourceGroup.user_id == user.id
    )
    granted_services = select(UserService.service_id).where(UserService.user_id == user.id)
    return or_(
        Service.resource_group_id.in_(granted_groups),
        Service.id.in_(granted_services),
    )
