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
- Single-function UI with proper input/output mapping
- Real-time calculation using `calc_eval`
- JSON result formatting

### basic_orchestrator.alp  
Multi-operation interface showing orchestration patterns:
- Operation selection dropdown
- Dynamic result formatting with markdown
- Technical details output

## 🚀 Usage

Run any example:
```bash
# Calculator UI
uv run python main.py examples/ui/simple_calculator.alp

# Orchestrator UI  
uv run python main.py examples/ui/basic_orchestrator.alp
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

1. **Function Mapping**: Ensure UI input names match your ALP function's input shape
2. **Error Handling**: UI system gracefully handles function execution errors
3. **Port Management**: Use different ports for multiple concurrent UIs
4. **Resource Cleanup**: `ui_wait` ensures proper server lifecycle management

## 🔧 Architecture

The UI system uses a declarative approach where:
1. **Configuration Phase**: Build UI structure with operations
2. **Handler Registration**: Connect ALP functions to UI events  
3. **Runtime Phase**: Gradio server executes ALP functions on user interaction
4. **Result Processing**: Automatic JSON formatting and error handling