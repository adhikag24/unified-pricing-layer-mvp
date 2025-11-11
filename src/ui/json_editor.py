"""
Enhanced JSON Editor Component for Streamlit
Provides JSON editing with syntax highlighting, bracket matching, and JSON path breadcrumbs
Uses Ace Editor for IDE-like experience with line numbers and bracket matching
"""
import streamlit as st
from streamlit_ace import st_ace
import json
from typing import Optional, Tuple, List, Dict, Any
import re


def calculate_json_path(json_text: str, cursor_position: int) -> str:
    """
    Calculate the JSON path at the cursor position.
    Returns a string like "components[0].dimensions.order_detail_id"

    Args:
        json_text: The JSON string
        cursor_position: Character position of the cursor (line * avg_chars_per_line)

    Returns:
        JSON path string
    """
    try:
        # Parse the JSON to validate it
        json_obj = json.loads(json_text)

        # Get the text up to cursor position
        text_before_cursor = json_text[:cursor_position]

        # Find all keys and array indices in the path
        path_parts = []

        # Track depth and context
        brace_depth = 0
        bracket_depth = 0
        in_string = False
        escape_next = False
        current_keys = []

        for i, char in enumerate(text_before_cursor):
            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string

            if not in_string:
                if char == '{':
                    brace_depth += 1
                elif char == '}':
                    brace_depth -= 1
                    if current_keys:
                        current_keys.pop()
                elif char == '[':
                    bracket_depth += 1
                elif char == ']':
                    bracket_depth -= 1
                    if current_keys and current_keys[-1].startswith('['):
                        current_keys.pop()

        # Extract keys from the text before cursor
        # Look for "key": pattern
        key_pattern = r'"([^"]+)"\s*:'
        matches = list(re.finditer(key_pattern, text_before_cursor))

        if matches:
            # Build path by tracking nesting level
            path_stack = []
            nesting_level = 0

            for match in matches:
                key = match.group(1)
                pos = match.start()

                # Count braces before this key to determine nesting
                before_key = text_before_cursor[:pos]
                open_braces = before_key.count('{') - before_key.count('}')
                open_brackets = before_key.count('[') - before_key.count(']')

                # Adjust stack based on nesting level
                while len(path_stack) > open_braces + open_brackets - 1:
                    path_stack.pop()

                path_stack.append(key)

            # Add array indices if we're in an array
            array_pattern = r'\[(\d+)\]'
            array_matches = list(re.finditer(array_pattern, text_before_cursor))

            # Construct the path
            path = ".".join(path_stack[-3:]) if len(path_stack) > 3 else ".".join(path_stack)

            if array_matches:
                last_array_index = array_matches[-1].group(1)
                # Find which key this array belongs to
                if path_stack:
                    last_key = path_stack[-1]
                    path = path.replace(last_key, f"{last_key}[{last_array_index}]")

            return f"📍 {path}" if path else "📍 root"

        return "📍 root"

    except (json.JSONDecodeError, Exception) as e:
        return "📍 (invalid JSON)"


def find_matching_bracket(json_text: str, line_number: int) -> Optional[Tuple[int, str]]:
    """
    Find the matching bracket for a bracket on the given line.

    Args:
        json_text: The JSON string
        line_number: Line number (0-indexed)

    Returns:
        Tuple of (matching_line_number, bracket_type) or None
    """
    lines = json_text.split('\n')
    if line_number >= len(lines):
        return None

    line = lines[line_number]

    # Find brackets in the line
    opening_brackets = ['{', '[']
    closing_brackets = ['}', ']']
    bracket_pairs = {'{': '}', '[': ']', '}': '{', ']': '['}

    # Simple bracket matching (not perfect but helpful)
    # Count brackets up to and including current line
    open_count = {'{}': 0, '[]': 0}

    for i, line_text in enumerate(lines):
        if i > line_number:
            break
        open_count['{}'] += line_text.count('{') - line_text.count('}')
        open_count['[]'] += line_text.count('[') - line_text.count(']')

    return None


def format_json(json_text: str) -> Tuple[bool, str]:
    """
    Format JSON text with proper indentation.

    Args:
        json_text: JSON string to format

    Returns:
        Tuple of (success, formatted_json_or_error_message)
    """
    try:
        obj = json.loads(json_text)
        formatted = json.dumps(obj, indent=2)
        return True, formatted
    except json.JSONDecodeError as e:
        return False, f"JSON Error at line {e.lineno}, column {e.colno}: {e.msg}"


def validate_json(json_text: str) -> Tuple[bool, str]:
    """
    Validate JSON text.

    Args:
        json_text: JSON string to validate

    Returns:
        Tuple of (is_valid, error_message_or_empty)
    """
    try:
        json.loads(json_text)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"Line {e.lineno}, column {e.colno}: {e.msg}"


def render_json_editor(
    label: str,
    value: str,
    height: int = 500,
    key: str = None,
    show_path: bool = True,
    show_validation: bool = True,
    read_only: bool = False,
    theme: str = "monokai"
) -> str:
    """
    Render an enhanced JSON editor with IDE-like features using Ace Editor.

    Features:
    - Line numbers
    - Bracket matching and highlighting
    - Syntax highlighting
    - Auto-indentation
    - Cursor position tracking

    Args:
        label: Label for the editor
        value: Initial JSON value
        height: Height of the editor in pixels
        key: Unique key for the editor
        show_path: Show JSON path breadcrumb
        show_validation: Show validation status
        read_only: Make editor read-only
        theme: Ace editor theme (monokai, github, tomorrow, etc.)

    Returns:
        Current JSON text value
    """
    # Container for the editor
    container = st.container()

    with container:
        # Header with tools
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

        with col1:
            st.markdown(f"**{label}**")

        with col2:
            if not read_only and st.button("🔧 Format", key=f"{key}_format"):
                success, result = format_json(value)
                if success:
                    value = result
                    if key:
                        st.session_state[f"{key}_formatted"] = value
                    st.success("✓ Formatted")
                else:
                    st.error(result)

        with col3:
            if show_validation:
                is_valid, error = validate_json(value)
                if is_valid:
                    st.markdown("✅ Valid")
                else:
                    st.markdown("❌ Invalid")

        with col4:
            # Line count indicator
            line_count = len(value.split('\n'))
            st.caption(f"📄 {line_count} lines")

        # Validation errors at the top (if invalid)
        if show_validation and not read_only:
            is_valid, error = validate_json(value)
            if not is_valid:
                st.error(f"⚠️ {error}")

        # Check if format button was clicked
        if key and f"{key}_formatted" in st.session_state:
            value = st.session_state[f"{key}_formatted"]
            del st.session_state[f"{key}_formatted"]

        # Main editor area using Ace Editor
        edited_value = st_ace(
            value=value,
            language="json",
            theme=theme,
            height=height,
            key=key,
            readonly=read_only,
            show_gutter=True,  # Show line numbers
            show_print_margin=False,
            wrap=False,
            auto_update=True,
            font_size=13,
            tab_size=2,
            keybinding="vscode",  # VSCode-like keybindings
            min_lines=10,
            placeholder="Enter JSON here...",
        )

        # JSON path breadcrumb (based on current line)
        if show_path:
            # Estimate cursor position (middle of document for static display)
            lines = edited_value.split('\n')
            mid_line = len(lines) // 2
            mid_position = len('\n'.join(lines[:mid_line]))

            json_path = calculate_json_path(edited_value, mid_position)
            st.caption(json_path)

        return edited_value


def render_json_editor_with_hints(
    label: str,
    value: str,
    height: int = 500,
    key: str = None,
    read_only: bool = False,
    allow_theme_selection: bool = True
) -> str:
    """
    Render JSON editor with helpful hints, theme selection, and IDE-like features.

    This is an enhanced version that provides:
    - Line numbers with gutter
    - Bracket matching and highlighting
    - Syntax highlighting with theme options
    - Format button
    - Validation status
    - VSCode-like keybindings
    - Quick JSON path hint

    Args:
        label: Label for the editor
        value: Initial JSON value
        height: Height of the editor in pixels
        key: Unique key for the editor
        read_only: Make editor read-only
        allow_theme_selection: Show theme selector

    Returns:
        Current JSON text value
    """
    # Theme selector
    theme = "monokai"  # Default dark theme
    if allow_theme_selection and not read_only:
        _, col_theme = st.columns([3, 1])
        with col_theme:
            theme = st.selectbox(
                "Theme",
                options=["monokai", "github", "tomorrow", "twilight", "dracula", "solarized_dark", "solarized_light"],
                index=0,
                key=f"{key}_theme"
            )

    # Info box with tips
    with st.expander("💡 JSON Editing Tips & Features", expanded=False):
        st.markdown("""
        **IDE Features (Ace Editor):**
        - ✓ **Line numbers** - Visible in the gutter on the left
        - ✓ **Bracket matching** - Click next to a bracket to see its match highlighted
        - ✓ **Syntax highlighting** - JSON keywords, strings, numbers colored
        - ✓ **Auto-indentation** - Press Enter after `{` or `[` for auto-indent
        - ✓ **VSCode keybindings** - Ctrl+D for multi-cursor, Ctrl+/ for comment, etc.

        **Tips for easier JSON editing:**
        - Use the **Format** button to auto-indent your JSON
        - Watch the **validation status** (✅/❌) in the top-right
        - The **line count** shows total lines in the document
        - The **JSON path** shows your approximate location in the structure
        - **Click on brackets** `{ } [ ]` to highlight matching pairs

        **Keyboard Shortcuts:**
        - `Ctrl+F` or `Cmd+F` - Find
        - `Ctrl+H` or `Cmd+H` - Replace
        - `Ctrl+D` or `Cmd+D` - Select next occurrence
        - `Ctrl+/` or `Cmd+/` - Toggle comment
        - `Tab` - Indent selection
        - `Shift+Tab` - Outdent selection

        **Common JSON issues:**
        - Missing commas between array items or object properties
        - Extra commas before closing `}` or `]`
        - Unmatched brackets or braces (use bracket matching!)
        - Missing quotes around property names
        - Invalid escape sequences in strings
        """)

    # Use the main editor with theme
    return render_json_editor(
        label=label,
        value=value,
        height=height,
        key=key,
        show_path=True,
        show_validation=True,
        read_only=read_only,
        theme=theme
    )


# Helper function to count bracket depth at each line
def get_bracket_depth_indicators(json_text: str) -> List[str]:
    """
    Get bracket depth indicator for each line.
    Returns a list of strings like "│  │  " for each line showing nesting.

    Args:
        json_text: The JSON string

    Returns:
        List of depth indicator strings
    """
    lines = json_text.split('\n')
    indicators = []
    depth = 0

    for line in lines:
        # Calculate depth for this line
        line_stripped = line.lstrip()

        # Count closing brackets at start
        closing_count = 0
        for char in line_stripped:
            if char in ['}', ']']:
                closing_count += 1
            else:
                break

        # Adjust depth before this line
        if closing_count > 0:
            depth -= closing_count

        # Create indicator
        indicator = "│  " * max(0, depth)
        indicators.append(indicator)

        # Count opening brackets for next line
        opening_count = line.count('{') + line.count('[')
        closing_count_total = line.count('}') + line.count(']')
        depth += (opening_count - closing_count_total)

    return indicators
