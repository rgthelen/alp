# ALP UI System

This directory contains examples of ALP programs that create interactive user interfaces using Gradio.

## ✨ Features

- **🔌 Seamless Integration**: UI operations are part of the ALP stdlib
- **🎯 Declarative**: Define UIs using ALP's JSON-based syntax
- **🚀 Orchestration**: Connect multiple ALP programs through UI
- **📱 Modern Interface**: Powered by Gradio for web-based UIs

## 📁 Examples

### simple_calculator.alp
A clean calculator interface demonstrating core UI concepts:
- **Imports** `calculator.alp` for core math logic
- **Delegates** calculations to imported functions
- **Handles** UI interaction and result display
- JSON result formatting

### basic_orchestrator.alp  
Multi-operation interface showing orchestration patterns:
- **Imports** core logic modules
- **Orchestrates** operations through UI selections
- Dynamic result formatting with markdown
- Technical details output

### advanced_orchestrator.alp
Comprehensive example demonstrating:
- **Multiple imports** from different logic modules
- **Conditional routing** based on user selection
- **Pure orchestration** without embedded logic
- Formatted and raw output options

## 🚀 Usage

Run any example:
```bash
# Calculator UI (port 7860)
uv run python main.py examples/ui/simple_calculator.alp

# Basic Orchestrator UI (port 7861)
uv run python main.py examples/ui/basic_orchestrator.alp

# Advanced Orchestrator UI (port 7862)
uv run python main.py examples/ui/advanced_orchestrator.alp
```

The UI will be available at the specified port (default: 7860).

## 🛠 UI Operations Reference

### Core Operations
- `ui_create(title, description, theme)` - Initialize UI configuration
- `ui_add_input(name, type, label, default, options)` - Add input component
- `ui_add_output(name, type, label)` - Add output component  
- `ui_set_handler(function, inputs, outputs)` - Connect ALP function
- `ui_launch(port, share, debug)` - Start Gradio server
- `ui_wait(timeout)` - Keep server running

### Input Component Types
- `textbox` - Text input with optional multiline support
- `number` - Numeric input with min/max validation
- `slider` - Range slider with step control
- `dropdown` - Selection from predefined options

### Output Component Types  
- `textbox` - Plain text display
- `json` - Formatted JSON with syntax highlighting
- `markdown` - Rich text with formatting support

## 🎯 Best Practices

### Separation of Concerns
1. **UI files** (`examples/ui/*.alp`) - Handle ONLY user interface and orchestration
2. **Logic files** (`examples/*.alp`) - Contain actual business logic and computations  
3. **Use `@import`** - UI files import logic modules rather than duplicating functionality

### Implementation Guidelines
1. **No Logic in UI**: UI files should not contain calculation or processing logic
2. **Import Core Modules**: Use `{"kind":"@import","path":"../calculator.alp"}` to reuse existing logic
3. **UI as Orchestrator**: UI functions orchestrate calls to imported logic functions
4. **Clear Naming**: Prefix UI-specific functions with `ui_` or use descriptive names
5. **Function Mapping**: Ensure UI input names match your ALP function's input shape
6. **Error Handling**: UI system gracefully handles function execution errors
7. **Port Management**: Use different ports for multiple concurrent UIs
8. **Resource Cleanup**: `ui_wait` ensures proper server lifecycle management

### Example Structure
```json
// GOOD: UI file imports and orchestrates
{"kind":"@import","path":"../calculator.alp"}
{"kind":"@fn","id":"ui_handler",
  "@op":[["calc_entry", {...}]]  // Uses imported function
}

// BAD: UI file contains logic
{"kind":"@fn","id":"ui_handler",
  "@op":[["calc_eval", {...}]]  // Direct logic in UI
}
```

## 🔧 Architecture

The UI system uses a declarative approach where:
1. **Configuration Phase**: Build UI structure with operations
2. **Handler Registration**: Connect ALP functions to UI events  
3. **Runtime Phase**: Gradio server executes ALP functions on user interaction
4. **Result Processing**: Automatic JSON formatting and error handling