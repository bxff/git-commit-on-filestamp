# Git Commit on Filestamp

![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Git](https://img.shields.io/badge/Git-2.0+-orange.svg)

A powerful Python script that automatically creates Git commits with timestamps based on file creation or modification dates. Perfect for backdating commits to match the actual timeline of your project's development.

## Features

### AI-Powered Commit Messages
- **Smart Message Generation**: Automatically generates descriptive commit messages using OpenAI-compatible APIs
- **Conventional Commit Format**: Follows best practices with formats like `feat:`, `fix:`, `docs:`, etc.
- **Intelligent Analysis**: Analyzes git diffs to understand the context of changes
- **Graceful Fallback**: Automatically falls back to simple date-based messages if AI generation fails

### Intelligent Timestamp Handling
- **File-Aware Timestamps**: Uses creation time for new files and modification time for existing files
- **Cross-Platform Support**: Works seamlessly on Windows, macOS, and Linux
- **Historical Accuracy**: Preserves the actual timeline of your project's development
- **Git Integration**: Properly sets both `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`

### Flexible Targeting
- **Single File Mode**: Commit individual files with their specific timestamps
- **Directory Mode**: Recursively process entire directories, committing files in chronological order
- **Smart Filtering**: Automatically respects `.gitignore` rules and skips the `.git` directory

### Rich Configuration
- **Environment-Based Setup**: Configure all settings via `.env` file
- **Multiple AI Providers**: Compatible with OpenAI and other OpenAI-compatible APIs
- **Customizable Limits**: Adjust diff character limits for AI processing
- **Author Configuration**: Set custom Git author name and email

## Quick Start

### 1. Installation

Clone the repository:
```bash
git clone https://github.com/bxff/git-commit-on-filestamp.git
cd git-commit-on-filestamp
```

Ensure you have Python 3.6+ and Git installed:
```bash
python --version
git --version
```

### 2. Configuration

Copy the example environment file and configure your settings:
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```env
# OpenAI-compatible API configuration
API_ENDPOINT=https://api.openai.com/v1/chat/completions
API_KEY=your-api-key-here
MODEL=gpt-3.5-turbo

# Git author configuration
GIT_AUTHOR_NAME=Your Name
GIT_AUTHOR_EMAIL=your.email@example.com

# Diff character limit for AI commit message generation
DIFF_CHAR_LIMIT=1000
```

### 3. Basic Usage

#### Commit a Single File
```bash
python main.py path/to/your/file.py
```

#### Commit an Entire Directory
```bash
python main.py path/to/your/directory
```

#### Use Custom Author Information
```bash
python main.py path/to/file.py --author "John Doe" --email "john@example.com"
```

#### Disable AI and Use Simple Messages
```bash
python main.py path/to/file.py --no-ai
```

## Detailed Usage

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `path` | Path to file or directory to commit | Required |
| `--author` | Git author name | From `.env` |
| `--email` | Git author email | From `.env` |
| `--no-ai` | Disable AI message generation | AI enabled |

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `API_ENDPOINT` | OpenAI-compatible API endpoint | Yes¹ | - |
| `API_KEY` | Your API key | Yes¹ | - |
| `MODEL` | AI model to use | Yes¹ | - |
| `GIT_AUTHOR_NAME` | Default Git author name | Yes² | - |
| `GIT_AUTHOR_EMAIL` | Default Git author email | Yes² | - |
| `DIFF_CHAR_LIMIT` | Max characters for AI diff analysis | No | `1000` |

¹ Required only when using AI-generated commit messages  
² Required for all operations

### How It Works

1. **File Analysis**: The script examines each file to determine if it's new (untracked) or modified
2. **Timestamp Extraction**: 
   - For new files: Uses the file creation time
   - For modified files: Uses the last modification time
3. **Git Status Check**: Respects `.gitignore` rules and skips ignored files
4. **Commit Message Generation**:
   - **AI Mode**: Analyzes git diff and generates contextual commit messages
   - **Fallback Mode**: Uses simple date-based messages
5. **Chronological Committing**: Files are committed in order of their timestamps

### Platform-Specific Behavior

#### Windows
- Uses `st_ctime` for file creation time
- Full compatibility with Git for Windows

#### macOS & Linux
- Prefers `st_birthtime` for creation time (when available)
- Falls back to `st_ctime` (inode change time) if needed
- Full compatibility with system Git installation

## Advanced Configuration

### Using Different AI Providers

The script supports any OpenAI-compatible API. Here are some examples:

#### OpenAI
```env
API_ENDPOINT=https://api.openai.com/v1/chat/completions
API_KEY=sk-your-openai-key
MODEL=gpt-3.5-turbo
```

#### Anthropic Claude (via OpenRouter)
```env
API_ENDPOINT=https://openrouter.ai/api/v1/chat/completions
API_KEY=sk-your-openrouter-key
MODEL=anthropic/claude-3.5-sonnet
```

#### Local LLM (Ollama)
```env
API_ENDPOINT=http://localhost:11434/v1/chat/completions
API_KEY=ollama
MODEL=llama3.2
```

### Performance Tuning

Adjust `DIFF_CHAR_LIMIT` based on your needs:
- **Lower values** (500-1000): Faster processing, less context
- **Higher values** (2000-5000): Better context, slower processing
- **Very high values** (10000+): Maximum context, may hit API limits
