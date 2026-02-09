from itertools import chain

from ask.ui.core.components import Element, Component, Box, Text, Widget
from ask.ui.core.styles import Axis, ansi_len
from ask.ui.core.tree import ElementTree, Offset

def layout(tree: ElementTree, element: Element, available_width: int | None = None, available_height: int | None = None) -> None:
    collapse_tree(tree, element)
    compute_lengths(tree, element, Axis.HORIZONTAL, available_width)
    compute_lengths(tree, element, Axis.VERTICAL, available_height)
    compute_offsets(tree, element)

def collapse_tree(tree: ElementTree, element: Element) -> None:
    tree.collapsed_children[element.uuid] = list(chain.from_iterable(collapse_children(tree, child) for child in tree.children[element.uuid]))
    for child in tree.collapsed_children[element.uuid]:
        collapse_tree(tree, child)

def collapse_children(tree: ElementTree, component: Component | None) -> list[Element]:
    match component:
        case None: return []
        case Widget(): return list(chain.from_iterable(collapse_children(tree, child) for child in tree.children[component.uuid]))
        case Element(): return [component] if component.visible else []
        case _: raise ValueError(f"Unknown component type: {type(component)}")

def compute_lengths(tree: ElementTree, element: Element, axis: Axis, available_length: int | None = None) -> None:
    flex = element.flex if isinstance(element, Box) else Axis.VERTICAL
    collapsed = tree.collapsed_children[element.uuid]
    child_lengths = [child.length(axis) for child in collapsed]
    computed_lengths = tree.widths if axis is Axis.HORIZONTAL else tree.heights

    if isinstance((element_length := element.length(axis)), int):
        available_length = min(available_length, element_length) if available_length is not None else element_length
    content_length = max(0, available_length - element.chrome(axis)) if available_length else None
    remaining_length = content_length

    # First: fixed-length children (int)
    for child, child_length in zip(collapsed, child_lengths, strict=True):
        if isinstance(child_length, int):
            compute_lengths(tree, child, axis, min(remaining_length, child_length) if remaining_length is not None else child_length)
            if flex is axis and remaining_length is not None:
                remaining_length = max(0, remaining_length - computed_lengths[child.uuid])

    # Second: flexible-length children (None)
    for child, child_length in zip(collapsed, child_lengths, strict=True):
        if child_length is None or (isinstance(child_length, float) and remaining_length is None):
            compute_lengths(tree, child, axis, remaining_length)
            if flex is axis and remaining_length is not None:
                remaining_length = max(0, remaining_length - computed_lengths[child.uuid])

    # Third: fractional-length children (float)
    if remaining_length is not None:
        total_fraction = sum(x for x in child_lengths if isinstance(x, float))
        scale = remaining_length / max(1, total_fraction) if flex is axis else float(remaining_length)
        for child, child_length in zip(collapsed, child_lengths, strict=True):
            if isinstance(child_length, float):
                scaled_length = min(remaining_length, int(child_length * scale))
                compute_lengths(tree, child, axis, scaled_length)
                remaining_length = max(0, remaining_length - computed_lengths[child.uuid])

    # Compute this element's length based on its length specification
    if isinstance(element_length, int):
        final_length = element_length
    elif isinstance(element_length, float):
        final_length = available_length or 0
    else:  # None - flexible, size to content
        if isinstance(element, Text):
            if axis is Axis.HORIZONTAL:
                wrapped = element.wrapped(content_length) if content_length else element.text.replace('\t', ' ' * 8)
                inner_length = max((ansi_len(line) for line in wrapped.split('\n')), default=0)
            else:  # VERTICAL - heights depend on widths for text wrapping
                content_width = max(0, tree.widths[element.uuid] - element.chrome(Axis.HORIZONTAL))
                wrapped = element.wrapped(content_width)
                inner_length = wrapped.count('\n') + 1 if wrapped else 0
        elif flex is axis:
            inner_length = sum((computed_lengths[c.uuid] for c in collapsed), start=0)
        else:
            inner_length = max((computed_lengths[c.uuid] for c in collapsed), default=0)
        final_length = inner_length + element.chrome(axis)

    computed_lengths[element.uuid] = min(available_length, final_length) if available_length is not None else final_length

def compute_offsets(tree: ElementTree, element: Element) -> None:
    flex = element.flex if isinstance(element, Box) else Axis.VERTICAL
    x_offset = element.margins['left'] + element.borders['left'] + element.paddings['left']
    y_offset = element.margins['top'] + element.borders['top'] + element.paddings['top']

    for child in tree.collapsed_children[element.uuid]:
        tree.offsets[child.uuid] = Offset(x=x_offset, y=y_offset)
        if flex is Axis.HORIZONTAL:
            x_offset += tree.widths[child.uuid]
        else:
            y_offset += tree.heights[child.uuid]
        compute_offsets(tree, child)
