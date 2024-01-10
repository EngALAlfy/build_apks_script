##############################################
#                                            #
#               Print module                 #
#           Response for operation           #
#           on print and styles              #
#                                            #
##############################################

class BColors:
    HEADER = ' '
    PRIMARY = ' '
    INFO = ' '
    SUCCESS = ' '
    WARNING = ' '
    DANGER = ' '
    ENDC = ' '
    BOLD = ' '
    UNDERLINE = ' '


def print_msg_box(msg, indent=1, width=None, title=None, color=BColors.BOLD):
    """Print message-box with optional title."""
    lines = msg.split('\n')
    space = " " * indent
    if not width:
        width = max(map(len, lines))
    box = f'╔{"═" * (width + indent * 2)}╗\n'  # upper_border
    if title:
        box += f'║{space}{title:<{width}}{space}║\n'  # title
        box += f'║{space}{"-" * len(title):<{width}}{space}║\n'  # underscore
    box += ''.join([f'║{space}{line:<{width}}{space}║\n' for line in lines])
    box += f'╚{"═" * (width + indent * 2)}╝'  # lower_border
    print(f"{color}{box}{BColors.ENDC}")


def danger(msg):
    return f"{BColors.DANGER}{msg}{BColors.ENDC}"


def success(msg):
    return f"{BColors.SUCCESS}{msg}{BColors.ENDC}"


def info(msg):
    return f"{BColors.INFO}{msg}{BColors.ENDC}"


def warning(msg):
    return f"{BColors.WARNING}{msg}{BColors.ENDC}"


def primary(msg):
    return f"{BColors.PRIMARY}{msg}{BColors.ENDC}"
