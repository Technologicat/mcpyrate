# -*- coding: utf-8; -*-
"""Colorize terminal output using Colorama."""

__all__ = ["setcolor", "colorize", "ColorScheme",
           "Fore", "Back", "Style"]

from colorama import init as colorama_init, Fore, Back, Style
colorama_init()

def setcolor(*colors):
    """Set color for ANSI terminal display.

    For available `colors`, see `Fore`, `Back` and `Style`.

    Each entry can also be a tuple (arbitrarily nested), which is useful
    for defining compound styles.
    """
    def _setcolor(color):
        if isinstance(color, (list, tuple)):
            return "".join(_setcolor(elt) for elt in color)
        return color
    return _setcolor(colors)

def colorize(text, *colors, reset=True):
    """Colorize string `text` for ANSI terminal display. Reset color at end of `text`.

    For available `colors`, see `Fore`, `Back` and `Style`.
    These are imported from `colorama`.

    Usage::

        colorize("I'm new here", Fore.GREEN)
        colorize("I'm bold and bluetiful", Style.BRIGHT, Fore.BLUE)

    Each entry can also be a tuple (arbitrarily nested), which is useful
    for defining compound styles::

        BRIGHT_BLUE = (Style.BRIGHT, Fore.BLUE)
        ...
        colorize("I'm bold and bluetiful, too", BRIGHT_BLUE)

    **CAUTION**: Does not nest. Style resets after the colorized text.
    """
    return "{}{}{}".format(setcolor(colors),
                           text,
                           setcolor(Style.RESET_ALL))


class ColorScheme:
    """The color scheme for debug utilities.

    See `Fore`, `Back`, `Style` in `colorama` for valid values. To make a
    compound style, place the values into a tuple.

    The defaults are designed to fit the "Solarized" (Zenburn-like) theme
    of `gnome-terminal`, with "Show bold text in bright colors" set to OFF.
    But they should work with most color schemes.
    """
    # ------------------------------------------------------------
    # unparse

    LANGUAGEKEYWORD = (Style.BRIGHT, Fore.YELLOW)
    DEFNAME = (Style.BRIGHT, Fore.CYAN)
    DECORATOR = Fore.LIGHTBLUE_EX

    STRING = Fore.GREEN
    NUMBER = Fore.GREEN
    NAMECONSTANT = Fore.GREEN  # True, False, None

    BUILTINEXCEPTION = Fore.CYAN
    BUILTINOTHER = Style.BRIGHT

    INVISIBLENODE = Style.DIM  # AST node with no surface syntax repr (Module, Expr)

    # AST markers for data-driven communication within the macro expander
    ASTMARKER = Style.DIM  # the "$AstMarker" title
    ASTMARKERCLASS = Fore.YELLOW  # the actual marker type name

    LINENUMBER = Style.DIM

    # ------------------------------------------------------------
    # step_expansion, StepExpansion, format_bindings

    # all
    HEADING = (Style.BRIGHT, Fore.LIGHTBLUE_EX)

    # step_expansion
    TREEID = (Style.NORMAL, Fore.LIGHTBLUE_EX)

    # format_bindings
    MACROBINDING = Style.BRIGHT
    GREYEDOUT = Style.DIM

    # StepExpansion
    ATTENTION = (Style.BRIGHT, Fore.GREEN)
    SOURCEFILENAME = Style.BRIGHT
    DIALECTTRANSFORMER = (Style.BRIGHT, Fore.YELLOW)

    _RESET = Style.RESET_ALL
