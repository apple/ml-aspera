from aspera.apps.company_directory import (
    Team,
    find_employee,
    find_team_of,
    get_current_user,
)
from aspera.apps.time_utils import combine, get_next_dow
from aspera.apps.work_calendar import Event, ShowAsStatus, add_event
from aspera.runtime_state_generation_tools.company_directory import (
    simulate_org_structure,
)


def setup_env_user_schedules_team_meeting():
    """Simulate the environment for the query:

    Query: Hey, [Assistant] put something in the calendar with my team at lunch tomorrow.
    """

    # TODO: SIMULATE THE ORGANISATION STRUCTURE TO ENSURE USER HAS A TEAM

    # Step 1: Simulate the org structure - by default the user will be assigned
    # to a team and `simulate_org_structure` docs state that if a subset of
    # employees is specified, additional names will be generated so that the
    # org structure is complete
    default_employee_names = []
    simulate_org_structure(default_employee_names)

    # NB: setting up events not necessary


def setup_env_user_schedules_user_schedules_meeting_with_manager_and_reports():
    """Simulate the environment for the query:

    Query: Hey, [Assistant], add an event with my manager and reports on the 5th of May at 10 in the morning.
    """
    # TODO: SIMULATE THE ORGANISATION WITH AN APPROPRIATE STRUCTURE SO THAT THE USER
    #  HAS BOTH MANAGER AND REPORTS

    # Step 1: Simulate the org structure - ensure the user has both reports and a manager
    #  so we will assign the user to a management role and extend their default team
    #  (Engineering) accordingly

    # we will use the default names for the basic organisation structure
    default_employee_names = []
    engineering_team_members = ["Pete", "Hector", "Anders", "Joris", "Tristan"]
    simulate_org_structure(
        default_employee_names,
        user_role="Manager",
        teams_to_extend={Team.Engineering: engineering_team_members},
    )

    # NB: setting up events not necessary


def setup_env_avoid_specific_attendees():
    """Simulate the environment for the query:

    Query: Hey, [Assistant] Make sure our team project planning is scheduled the
    thursday after next at 14:30. Ben and Jerry don't need to attend because
    they're on a different project.
    """

    # TODO: SIMULATE THE ORGANISATION STRUCTURE, ENSURING BEN, JERRY AND THE USER
    #  ARE IN THE SAME TEAM

    # Step 1: To ensure Ben, Jerry and the user are in the same team, we will
    # create the default organisation and then extend user's team with several
    # other members, including Ben and Jerry
    default_employee_names = []
    user_team = Team.Finance
    finance_team_members = ["Ben", "Jerry", "Tom", "Jack", "William"]
    simulate_org_structure(
        default_employee_names,
        user_team=user_team,
        teams_to_extend={user_team: finance_team_members},
    )

    # NB: setting up events not necessary


def setup_env_modify_existing_event_start_time():
    """Simulate the environment for the query:

    Query: Hey, [Assistant] Would you mind pushing back
     my catch-up meeting with Pete taking place next Tuesday by 23 minutes?
    """

    # TODO: SIMULATE THE ORGANISATION STRUCTURE, ENSURING PETE IS A MEMBER
    #  OF THE ORGANISATION. SPECIFY THE NAMES OF 3 OTHER MEMBERS
    # TODO: CREATE THE EVENT THE USER REFERS TO ("QUERY_EVENT"), USING APPROPRIATE TIME_UTILS TOOLS
    # TODO: CREATE THREE OTHER CONFOUNDER EVENTS THAT TEST THE AGENT UNDERSTANDING

    # import locally any standard libray modules you need for the program
    import datetime
    from datetime import timedelta

    # Step 1: Create org, with Pete & 3 others amongst the default
    # employee names
    default_employee_names = ["Pete", "Olga", "Anna", "Serena"]
    simulate_org_structure(default_employee_names)
    # Step 2: Ensure the event referenced in the query exists in the user's calendar
    # setup guideline #1
    meeting_date = get_next_dow("Tuesday")
    # setup guideline #2
    meeting_start_time = datetime.time(hour=13, minute=30)
    meeting_end_time = datetime.time(hour=14, minute=0)
    starts_at = combine(meeting_date, meeting_start_time)
    ends_at = combine(meeting_date, meeting_end_time)
    # setup guideline #3
    attendees = [find_employee("Pete")[0]]
    subject = "Catch-up"
    query_event = Event(
        attendees=attendees, starts_at=starts_at, ends_at=ends_at, subject=subject
    )
    add_event(query_event)
    # Step 3: Create three other events to test understanding
    # a catch-up with pete the day before
    confounder_1 = Event(
        attendees=attendees,
        starts_at=starts_at - timedelta(days=1),
        ends_at=ends_at - timedelta(days=1),
        subject=subject,
    )
    add_event(confounder_1)
    # a catch-up with Pete on Thursday
    confounder_2 = Event(
        attendees=attendees,
        starts_at=starts_at + timedelta(days=2),
        ends_at=ends_at + timedelta(days=2),
        subject=subject,
    )
    add_event(confounder_2)
    # a catch-up with Anna on the same day
    # setup guideline #3
    attendees = [find_employee("Anna")[0]]
    confounder_3 = Event(
        attendees=attendees,
        starts_at=starts_at - timedelta(hours=3),
        ends_at=ends_at - timedelta(hours=3),
        subject=subject,
    )
    add_event(confounder_3)


def setup_env_busiest_day_this_week():
    """Simulate the environment for the query:

    Query: Hey, [Assistant], my busiest day this week?
    """

    # TODO: SIMULATE A BASIC ORGANISATION STRUCTURE SO THAT EVENTS HAVE ATTENDEES
    # TODO: BUSIEST DAY IS JUNE 26TH 2024 WITH A 5 HOUR EVENT
    # TODO: CREATE CONFOUNDING EVENTS IN TWO OTHER DAYS, TO TEST AGENT UNDERSTANDING

    # import locally any standard libray modules you need for the program
    import datetime
    from datetime import timedelta

    # Step 1: Simulate the organisation structure - we only need it so that we
    #  create the user details and to add meeting attendees
    default_employee_names = ["Dean", "Jeniffer", "Helen", "Jack", "William"]
    simulate_org_structure(default_employee_names)

    # Step 2: Create busiest day
    starts_at = datetime.datetime(year=2024, day=26, month=6, hour=10, minute=5)
    ends_at = starts_at + timedelta(hours=5)
    event = Event(
        # setup guideline #3
        attendees=[find_employee("Dean")[0]],
        starts_at=starts_at,
        ends_at=ends_at,
        subject="Training with Dean",
    )
    add_event(event)
    # Step 3:
    # day 1: less busy day with two events lasting 15 minutes
    user = get_current_user()
    first_start = datetime.datetime(year=2024, day=27, month=6, hour=10, minute=5)
    first_ends = starts_at + timedelta(minutes=15)
    event = Event(
        attendees=find_team_of(user),
        starts_at=first_start,
        ends_at=first_ends,
        subject="Stand-up",
    )
    add_event(event)
    second_start = first_start + timedelta(hours=6)
    second_ends = second_start + timedelta(minutes=15)
    event = Event(
        attendees=find_team_of(user),
        starts_at=second_start,
        ends_at=second_ends,
        subject="Afternoon Stand-up",
    )
    add_event(event)
    # day 2: a very busy day the week after
    starts_at = datetime.datetime(year=2024, day=1, month=7, hour=10, minute=0)
    ends_at = datetime.datetime(year=2024, day=1, month=7, hour=17, minute=0)
    event = Event(
        show_as_status=ShowAsStatus.OutOfOffice,
        starts_at=starts_at,
        ends_at=ends_at,
        subject="Customer site training",
        location="123 Fantasia Road, Cambridge UK",
    )
    add_event(event)
