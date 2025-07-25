class RequiresUserInput(Exception):
    """An exception to be raised when an assumption has to be made in order
    to continue the program. Typical situations involve:

        - indexing search results when multiple or no search results are returned
        but the user query implies the uniqueness of the search results.
        - inform the user a task could not be completed (eg no suitable meeting
        room could be booked for a meeting as per the user request).


    For additional details, consult program structure guidelines below (displayed
     only if any special guidance applies).

    Notes
    -----
    1. Cases when no or multiple search results are returned should have distinct messages
     to indicate why the error was raised.
    2. The number of returned results should always be stated when the error is raised because
     a search returned more than one result.
    3. This error *should not* be raised to respond to user questions - an appropriate object
    should be returned instead. However, if the question cannot be answered (eg user asks
    about meeting which cannot be found), then this exception can be raised.
    4. If the user warns the assistant of possible conflicts when making their request (eg
    schedule something if it doesn't conflict with something else), this error should not be raised.
    5. Employee names can be assumed unique unless the user request implies this is not the case. In this
    case it is not necessary to raise this error and raising it will have no effect."""
