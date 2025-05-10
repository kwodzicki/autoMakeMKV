"""
Utilities for building file names/paths

When ripping titles, output files must match
naming convention of video_utils package
ingest. These functions ensure that the
file names match what are expected by that
program suite.

"""

import re

# Characters that are not allowed in file paths
BADCHARS = re.compile(r'[#%\\\<\>\*\?/\$\!\:\@]')


def replace_chars(*args, repl: str = ' ', **kwargs):
    """
    Replace invalid path characters; '&' replaced with 'and'

    Arguments:
        *args (str): String(s) to replace characters in

    Keyword arguments:
        repl (str): String to replace bad characters with;
            default is space (' ')
        **kwargs

    Returns:
        String, or list, with bad values replaced by repl value

    """

    # If one input argument
    if len(args) == 1:
        return _replace(args[0], repl, **kwargs)

    # Iterate over all input arguments, returning list
    return [
        _replace(arg, repl, **kwargs)
        for arg in args
    ]


def _replace(string: str, repl: str, **kwargs) -> str:
    """
    'Private' function for replace characters in string

    Arguments:
        string (str): String to have characters replaced
        repl (str): String to replace bad characters with

    Keyword arguments:
        **kwargs: Any, none used currently

    Returns:
        str: String with bad values repaced by repl value

    """

    return BADCHARS.sub(repl, string).replace('&', 'and').strip()
