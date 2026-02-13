def is_light(rgb: tuple[int, int, int]) -> bool:
    red, green, blue = rgb
    luma = 0.299 * red + 0.587 * green + 0.114 * blue
    return luma > 128.0

class Theme:
    RED = '#FF6B80'
    DARK_RED = '#7A2936'
    FADED_RED = '#69484D'
    LIGHT_ORANGE = '#EB9F7F'
    ORANGE = '#D77757'
    GREEN = '#4EBA65'
    DARK_GREEN = '#225C2B'
    FADED_GREEN = '#47584A'
    BLUE = '#B1B9F9'
    PURPLE = '#A669FF'
    DARK_PURPLE = '#482F70'
    PINK = '#FD5DB1'
    GRAY = '#AAAAAA'
    DARK_GRAY = '#888888'
    WHITE = '#FFFFFF'
