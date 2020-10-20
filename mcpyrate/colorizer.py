# -*- coding: utf-8; -*-
"""Colorize terminal output using Colorama."""

__all__ = ["setcolor", "colorize", "ColorScheme",
           "Fore", "Back", "Style"]

from colorama import init as colorama_init, Fore, Back, Style


colorama_init()


def setcolor(*colors):
    """Set color for terminal display.

    Returns a string that, when printed into a terminal, sets the color
    and style. We use `colorama`, so this works on any OS.

    For available `colors`, see `Fore`, `Back` and `Style`.
    These are imported from `colorama`.

    Each entry can also be a tuple (arbitrarily nested), which is useful
    for defining compound styles.

    **CAUTION**: The specified style and color remain in effect until another
    explicit call to `setcolor`. To reset, use `setcolor(Style.RESET_ALL)`.
    If you want to colorize a piece of text so that the color and style
    auto-reset after your text, use `colorize` instead.
    """
    def _setcolor(color):
        if isinstance(color, (list, tuple)):
            return "".join(_setcolor(elt) for elt in color)
        return color
    return _setcolor(colors)


def colorize(text, *colors, reset=True):
    """Colorize string `text` for terminal display.

    Returns `text`, augmented with color and style commands for terminals.
    We use `colorama`, so this works on any OS.

    For available `colors`, see `Fore`, `Back` and `Style`.
    These are imported from `colorama`.

    Usage::

        print(colorize("I'm new here", Fore.GREEN))
        print(colorize("I'm bold and bluetiful", Style.BRIGHT, Fore.BLUE))

    Each entry can also be a tuple (arbitrarily nested), which is useful
    for defining compound styles::

        BRIGHT_BLUE = (Style.BRIGHT, Fore.BLUE)
        ...
        print(colorize("I'm bold and bluetiful, too", BRIGHT_BLUE))

    **CAUTION**: Does not nest. Style and color reset after the colorized text.
    If you want to set a color and style until further notice, use `setcolor`
    instead.
    """
    return "{}{}{}".format(setcolor(colors),
                           text,
                           setcolor(Style.RESET_ALL))


class ColorScheme:
    """The color scheme for terminal output in `mcpyrate`'s debug utilities.

    This is just a bunch of constants. To change the colors, simply assign new
    values to them. Changes take effect immediately for any new output.

    (Don't replace the `ColorScheme` class itself, though; all the use sites
    from-import it.)

    See `Fore`, `Back`, `Style` in `colorama` for valid values. To make a
    compound style, place the values into a tuple.

    The defaults are designed to fit the "Solarized" (Zenburn-like) theme
    of `gnome-terminal`, with "Show bold text in bright colors" set to OFF.
    But they work also with "Tango", and indeed with most themes.
    """
    _RESET = Style.RESET_ALL

    # ------------------------------------------------------------
    # unparse

    LINENUMBER = Style.DIM

    LANGUAGEKEYWORD = (Style.BRIGHT, Fore.YELLOW)  # for, if, import, ...

    DEFNAME = (Style.BRIGHT, Fore.CYAN)  # name of a function or class being defined
    DECORATOR = Fore.LIGHTBLUE_EX

    STRING = Fore.GREEN
    NUMBER = Fore.GREEN
    NAMECONSTANT = Fore.GREEN  # True, False, None

    BUILTINEXCEPTION = Fore.CYAN
    BUILTINOTHER = Style.BRIGHT  # str, property, print, ...

    INVISIBLENODE = Style.DIM  # AST node with no surface syntax repr (Module, Expr)

    # AST markers for data-driven communication within the macro expander
    ASTMARKER = Style.DIM  # the "$AstMarker" title
    ASTMARKERCLASS = Fore.YELLOW  # the actual marker type name

    # ------------------------------------------------------------
    # format_bindings, step_expansion, StepExpansion

    HEADING = (Style.BRIGHT, Fore.LIGHTBLUE_EX)
    SOURCEFILENAME = (Style.BRIGHT, Fore.RESET)

    # format_bindings
    MACROBINDING = (Style.BRIGHT, Fore.RESET)
    GREYEDOUT = Style.DIM

    # step_expansion
    TREEID = (Style.NORMAL, Fore.LIGHTBLUE_EX)

    # StepExpansion
    ATTENTION = (Style.BRIGHT, Fore.GREEN)  # the string "DialectExpander debug mode"
    DIALECTTRANSFORMER = (Style.BRIGHT, Fore.YELLOW)

    # ------------------------------------------------------------
    # dump

    NODETYPE = (Style.BRIGHT, Fore.LIGHTBLUE_EX)
    FIELDNAME = Fore.YELLOW
    BAREVALUE = Fore.GREEN
