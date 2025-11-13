# JSON Editor Enhancements - IDE-Like Experience

## Overview

The JSON editor has been upgraded from basic `st.text_area` to a full-featured **Ace Editor** integration, providing a VSCode-like editing experience directly in the Streamlit UI.

## New Features

### ✅ Line Numbers
- **Visible line numbers** in the gutter (left side)
- Makes it easy to reference specific lines when debugging
- Matches the read-only code view style

### ✅ Bracket Matching & Highlighting
- **Click next to any bracket** `{ } [ ]` to see its matching pair highlighted
- Visual feedback showing which opening bracket belongs to which closing bracket
- Helps navigate deeply nested JSON structures
- Prevents unmatched bracket errors

### ✅ Syntax Highlighting
- **Color-coded JSON elements**:
  - Keys (property names) in one color
  - String values in another color
  - Numbers, booleans, null in distinct colors
  - Brackets and structural elements highlighted
- Improves readability and error detection

### ✅ Theme Selection
- **7 theme options** to choose from:
  - `monokai` (default dark theme)
  - `github` (light theme)
  - `tomorrow` (light theme)
  - `twilight` (dark theme)
  - `dracula` (dark theme with purple accents)
  - `solarized_dark`
  - `solarized_light`
- Selector appears in edit mode (not read-only)

### ✅ Auto-Indentation
- Press `Enter` after `{` or `[` for automatic indentation
- Maintains consistent 2-space indentation
- Tab/Shift+Tab for manual indent/outdent

### ✅ VSCode Keybindings
All familiar keyboard shortcuts work:
- `Ctrl+F` / `Cmd+F` - Find
- `Ctrl+H` / `Cmd+H` - Replace
- `Ctrl+D` / `Cmd+D` - Select next occurrence (multi-cursor)
- `Ctrl+/` / `Cmd+/` - Toggle comment
- `Tab` - Indent selection
- `Shift+Tab` - Outdent selection

### ✅ Real-Time Validation
- **Validation status badge** (✅ Valid / ❌ Invalid)
- **Error messages** with line and column numbers
- Displayed at the top of the editor (no need to scroll)

### ✅ Format Button
- One-click JSON formatting
- Auto-indents and prettifies JSON
- Shows success/error feedback

### ✅ Line Count Indicator
- Shows total number of lines in the document
- Useful for tracking document size

### ✅ JSON Path Breadcrumb
- Displays approximate path in JSON structure
- Format: `📍 path.to.current.location`
- Helps orient yourself in large documents

## Usage

### Basic Editor

```python
from src.ui.json_editor import render_json_editor

edited_json = render_json_editor(
    label="Edit event data (JSON Mode - no form interference)",
    value=initial_json_string,
    height=600,
    key="event_json_editor",
    show_path=True,
    show_validation=True,
    read_only=False,
    theme="monokai"  # Optional: default is monokai
)
```

### Editor with Tips & Theme Selector

```python
from src.ui.json_editor import render_json_editor_with_hints

edited_json = render_json_editor_with_hints(
    label="Edit event data (JSON Mode - no form interference)",
    value=initial_json_string,
    height=600,
    key="event_json_editor",
    read_only=False,
    allow_theme_selection=True  # Shows theme dropdown
)
```

## Technical Details

### Dependencies
- **streamlit-ace**: Ace Editor integration for Streamlit
- Installed via: `pip install streamlit-ace`

### Ace Editor Configuration
```python
st_ace(
    value=json_string,
    language="json",
    theme="monokai",
    height=500,
    readonly=False,
    show_gutter=True,        # Line numbers enabled
    show_print_margin=False, # No print margin line
    wrap=False,              # No word wrap (better for JSON)
    auto_update=True,        # Real-time updates
    font_size=13,
    tab_size=2,              # 2-space indentation
    keybinding="vscode",     # VSCode shortcuts
    min_lines=10,
    placeholder="Enter JSON here..."
)
```

## Comparison: Before vs After

| Feature | Before (st.text_area) | After (Ace Editor) |
|---------|----------------------|-------------------|
| Line numbers | ❌ No | ✅ Yes |
| Bracket matching | ❌ No | ✅ Yes (click to highlight) |
| Syntax highlighting | ❌ No | ✅ Yes (full JSON syntax) |
| Themes | ❌ System default only | ✅ 7 themes |
| Auto-indent | ❌ No | ✅ Yes (smart indentation) |
| Keyboard shortcuts | ⚠️ Basic text editing | ✅ Full IDE shortcuts |
| Multi-cursor | ❌ No | ✅ Yes (Ctrl+D) |
| Find/Replace | ❌ Browser only | ✅ Built-in (Ctrl+F/H) |
| Code folding | ❌ No | ⚠️ Limited (future enhancement) |

## Known Limitations

1. **JSON Path Breadcrumb**: Currently shows approximate location (mid-document). Real-time cursor position tracking requires additional JavaScript integration.

2. **Code Folding**: Not yet implemented. Future enhancement could add collapsible sections for large JSON arrays/objects.

3. **Format on Save**: Auto-format on blur is not enabled. Users must click the Format button explicitly.

## Future Enhancements

### Potential Improvements
- [ ] Real-time cursor position tracking for JSON path
- [ ] Code folding/collapsing for nested structures
- [ ] Minimap for large documents
- [ ] Diff view for comparing JSON versions
- [ ] Custom snippets/templates
- [ ] Error squiggles (like VSCode red underlines)

## Files Modified

1. **src/ui/json_editor.py**
   - Imported `streamlit_ace`
   - Updated `render_json_editor()` to use Ace Editor
   - Enhanced `render_json_editor_with_hints()` with theme selector
   - Added comprehensive help text with keyboard shortcuts

2. **requirements.txt** (should be updated)
   - Add: `streamlit-ace>=0.1.1`

## Testing Checklist

- [x] Editor loads with default theme (monokai)
- [x] Line numbers visible in gutter
- [x] Bracket matching works (click on `{` highlights `}`)
- [x] Syntax highlighting applied correctly
- [x] Theme selector changes theme
- [x] Format button works
- [x] Validation shows errors with line numbers
- [x] VSCode keybindings functional
- [x] Read-only mode works
- [x] Integration with producer playground

## Deployment Notes

When deploying, ensure:
1. `streamlit-ace` is in `requirements.txt` or `environment.yml`
2. No conflicts with existing Streamlit version (tested with Streamlit 1.51.0)
3. Browser compatibility: Ace Editor works on all modern browsers

## Documentation

The editor now includes built-in help accessible via the "💡 JSON Editing Tips & Features" expander, covering:
- IDE features overview
- Editing tips
- Keyboard shortcuts reference
- Common JSON issues to avoid
