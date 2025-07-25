from aspera.apps.company_directory import Employee, find_manager_of, get_current_user


def skip_manager_name() -> str:
    """Find skip manager name

    Query: Hey, [Assistant], my busiest day this week?
    """

    # find user's profile
    user = get_current_user()
    # find the manager
    manager: Employee = find_manager_of(user)
    # find skip manger
    skip_manager = find_manager_of(manager)
    # return the name
    return skip_manager.name
