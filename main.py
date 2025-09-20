import os
import sys
import argparse
from datetime import datetime
import subprocess
import requests
import re
import platform
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI-compatible API configuration
API_ENDPOINT = os.getenv("API_ENDPOINT")
API_KEY = os.getenv("API_KEY")
MODEL = os.getenv("MODEL")
DIFF_CHAR_LIMIT = int(os.getenv("DIFF_CHAR_LIMIT", "1000")) # Default to 1000 if not set

# Git author configuration
GIT_AUTHOR_NAME = os.getenv("GIT_AUTHOR_NAME")
GIT_AUTHOR_EMAIL = os.getenv("GIT_AUTHOR_EMAIL")



def get_file_timestamps(file_path):
    """
    Get creation and modification timestamps for a file.
    Returns a tuple of (creation_time, modification_time) as datetime objects.
    """
    try:
        stat_info = os.stat(file_path)
        
        # Get modification time (available on all platforms)
        mod_time = datetime.fromtimestamp(stat_info.st_mtime)
        
        # Get creation time (platform-specific)
        if platform.system() == 'Windows':
            # On Windows, st_ctime is creation time
            creation_time = datetime.fromtimestamp(stat_info.st_ctime)
        else:
            # On Unix/Mac, st_birthtime is creation time if available
            # Fall back to st_ctime (inode change time) if st_birthtime is not available
            if hasattr(stat_info, 'st_birthtime'):
                creation_time = datetime.fromtimestamp(stat_info.st_birthtime)
            else:
                creation_time = datetime.fromtimestamp(stat_info.st_ctime)
        
        return creation_time, mod_time
    except Exception as e:
        print(f"Error getting timestamps for {file_path}: {e}")
        # Fallback to current time if we can't get timestamps
        current_time = datetime.now()
        return current_time, current_time

def is_file_ignored(file_path):
    """
    Check if a file is ignored by .gitignore.
    Returns True if the file is ignored, False otherwise.
    """
    try:
        # Use git check-ignore to determine if file is ignored
        result = subprocess.run(
            ["git", "check-ignore", file_path],
            capture_output=True,
            text=True,
            check=False  # Don't raise exception for ignored files
        )
        
        # If git check-ignore returns 0, the file is ignored
        # If it returns 1, the file is not ignored
        # If it returns 128+, there was an error
        if result.returncode == 0:
            return True  # File is ignored
        elif result.returncode == 1:
            return False  # File is not ignored
        else:
            # Error occurred, assume not ignored to be safe
            print(f"Warning: Error checking git ignore status for {file_path}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Unexpected error checking git ignore status for {file_path}: {e}")
        return False

def is_file_new(file_path):
    """
    Check if a file is new (untracked or added but not committed).
    Returns True if the file is new, False if it's modified.
    """
    try:
        # Get git status for the file
        result = subprocess.run(
            ["git", "status", "--porcelain", file_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        status_line = result.stdout.strip()
        if not status_line:
            # If no status output, file might be committed and unchanged
            return False
        
        # Check the status code
        status_code = status_line[:2]
        
        # Files with status '??' are untracked (new)
        # Files with status 'A ' are added to staging area (new)
        # Files with status 'M ' are modified
        # Files with status ' M' are modified but not staged
        
        return status_code in ['??', 'A ']
        
    except subprocess.CalledProcessError as e:
        print(f"Error checking git status for {file_path}: {e}")
        # If we can't determine status, assume it's modified to be safe
        return False
    except Exception as e:
        print(f"Unexpected error checking file status for {file_path}: {e}")
        return False

def get_appropriate_timestamp(file_path):
    """
    Get the appropriate timestamp for a file based on its status.
    Returns creation time for new files, modification time for modified files.
    """
    creation_time, mod_time = get_file_timestamps(file_path)
    
    if is_file_new(file_path):
        print(f"File {file_path} is new, using creation time: {creation_time}")
        return creation_time
    else:
        print(f"File {file_path} is modified, using modification time: {mod_time}")
        return mod_time

def generate_commit_message_with_ai(file_paths):
    """
    Generates a commit message using an OpenAI-compatible API based on git diff.
    Returns None if AI generation fails.
    """
    if not API_ENDPOINT or not API_KEY or not MODEL:
        print("Error: API_ENDPOINT, API_KEY, or MODEL not set in .env file.")
        return None # Return None to indicate failure and trigger fallback

    try:
        # Get the staged changes (diff) for the specified files
        # Using --cached to get staged changes, and -- to separate paths from revision
        result = subprocess.run(
            ["git", "diff", "--cached", "--"] + file_paths,
            capture_output=True,
            text=True,
            check=True
        )
        diff_output = result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}")
        return None # Return None to indicate failure and trigger fallback
    except FileNotFoundError:
        print("Error: git command not found. Is Git installed and in your PATH?")
        return None # Return None to indicate failure and trigger fallback

    truncated_notice = ""
    if len(diff_output) > DIFF_CHAR_LIMIT:
        diff_output = diff_output[:DIFF_CHAR_LIMIT]
        truncated_notice = "Note: The git diff was too long and has been truncated.\n"

    if not diff_output.strip():
        # If there are no staged changes, it might be a new file.
        # We can try to get the diff of the working directory against /dev/null for new files.
        # However, a simpler approach is to inform the user or handle it as a special case.
        # For now, let's check if the files are new and untracked.
        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"] + file_paths,
                capture_output=True,
                text=True,
                check=True
            )
            # Check for 'A' (added) or '??' (untracked) files
            if any(line.startswith('A') or line.startswith('??') for line in status_result.stdout.splitlines()):
                # For new files, we'll read their content as a fallback
                file_contents = ""
                for file_path in file_paths:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Also truncate new file content if it's too long
                            if len(content) > DIFF_CHAR_LIMIT:
                                content = content[:DIFF_CHAR_LIMIT]
                                truncated_notice = "Note: The new file content was too long and has been truncated.\n"
                            file_contents += f"--- New File: {os.path.basename(file_path)} ---\n{content[:500]}...\n\n"
                    except UnicodeDecodeError:
                        # File is binary, note this and skip content reading
                        file_contents += f"--- New File: {os.path.basename(file_path)} ---\n(Binary file - content not displayed)\n\n"
                    except Exception as e:
                        print(f"Warning: Could not read new file {file_path}: {e}")
                        file_contents += f"--- New File: {os.path.basename(file_path)} ---\n(Could not read file content)\n\n"
                diff_output = file_contents if file_contents else "No changes detected and files are not new or readable."
            else:
                diff_output = "No staged changes detected for the specified files."
        except Exception as e:
            print(f"Error checking git status for new files: {e}")
            diff_output = "No staged changes and could not determine if files are new."


    prompt = f"""
    Analyze the following git diff output to generate a descriptive Git commit message.
    The message should follow the conventional commit format (e.g., 'feat: add new feature', 'fix: resolve bug in login', 'docs: update README', 'style: format code', 'refactor: simplify function', 'test: add unit tests', 'chore: update dependencies').
    If the changes seem incomplete or are a work in progress, use 'wip: ...'.
    Keep the message concise and under 72 characters for the subject line.
    {truncated_notice}
    Git Diff:
    {diff_output}

    Commit Message:
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert assistant that generates concise and descriptive Git commit messages following conventional commit formats. Be brief in your reasoning and prioritize generating the commit message itself."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 600, # Significantly increased max_tokens
        "temperature": 0.5,
    }

    try:
        response = requests.post(API_ENDPOINT, headers=headers, json=data, timeout=30)
        response.raise_for_status()  # Raise an exception for HTTP errors
        response_json = response.json()
        message = response_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        # Clean up common AI artifacts like quotes or extra newlines
        message = re.sub(r'^"|"$', '', message) # Remove leading/trailing quotes
        message = re.sub(r'\n+', ' ', message) # Replace multiple newlines with a space
        return message if message else None
    except requests.exceptions.RequestException as e:
        print(f"Error calling AI API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            # In case of API error, print the response text for debugging
            print(f"API Error Response Text: {e.response.text}")
        return None # Return None to indicate failure and trigger fallback
    except KeyError as e:
        print(f"Error: Unexpected response format from AI API. Missing key: {e}")
        # It's good to have the response text for debugging unexpected formats
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"Full API Response Text: {response.text}")
        return None # Return None to indicate failure and trigger fallback
    except Exception as e:
        print(f"An unexpected error occurred during AI message generation: {e}")
        return None # Return None to indicate failure and trigger fallback


def commit_files(files, datetime_obj, author, author_email, use_ai_for_message=False):
    print(f"Preparing to commit files: {files}")
    for file in files:
        subprocess.run(["git", "add", file], check=True)

    # Use the full datetime with precise time, not just date at midnight
    commit_date = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")

    if use_ai_for_message:
        print("Generating commit message with AI...")
        commit_message = generate_commit_message_with_ai(files)
        if commit_message is None:
            return None # Signal failure to trigger fallback in main()
    else:
        commit_message = f"Adding files from {datetime_obj.date()}"

    if commit_message is None: # Should not happen if not AI, but as a safeguard
        print("Error: Commit message is None, cannot proceed with commit.")
        return None

    print(f"Using commit message: '{commit_message}'")
    print(f"Using commit timestamp: {commit_date}")

    env = os.environ.copy()
    # Here'This is the most important bit: these environment variables are used
    # by Git to set the author and committer dates and names
    env["GIT_AUTHOR_DATE"] = commit_date
    env["GIT_COMMITTER_DATE"] = commit_date
    env["GIT_AUTHOR_NAME"] = author
    env["GIT_AUTHOR_EMAIL"] = author_email
    env["GIT_COMMITTER_NAME"] = author
    env["GIT_COMMITTER_EMAIL"] = author_email

    try:
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        commit_hash = result.stdout.split()[1]
        print(f"Successfully committed: {commit_hash}, DateTime: {datetime_obj}, Message: '{commit_message}'")
        return commit_hash
    except subprocess.CalledProcessError as e:
        print(f"Error during git commit: {e.stderr}")
        return None
    except IndexError:
        print("Error: Could not parse commit hash from git output.")
        print(f"Git stdout: {result.stdout}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Populate Git repo with historical commits, using AI for messages by default with fallback."
    )
    parser.add_argument("path", help="Path to a file or directory to commit.")
    parser.add_argument("--author", help="Author of the commits (defaults to GIT_AUTHOR_NAME from .env)")
    parser.add_argument("--email", help="Email of author (defaults to GIT_AUTHOR_EMAIL from .env)")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI and use default commit messages.")
    args = parser.parse_args()

    # Use environment variables for author/email if not provided via CLI
    author_name = args.author if args.author else GIT_AUTHOR_NAME
    author_email = args.email if args.email else GIT_AUTHOR_EMAIL

    if not author_name or not author_email:
        print("Error: Author name and email must be provided either via --author/--email arguments or set in .env file (GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL).")
        sys.exit(1)

    # Determine the actual directory for git operations and if the target is a single file
    abs_target_path = os.path.abspath(args.path)
    is_single_file = os.path.isfile(abs_target_path)
    is_directory = os.path.isdir(abs_target_path)

    if not is_single_file and not is_directory:
        print(f"Error: Path '{args.path}' (resolved to '{abs_target_path}') is not a valid file or directory.")
        sys.exit(1)

    if is_single_file:
        target_path = abs_target_path
        git_repo_dir = os.path.dirname(target_path)
    else: # It's a directory
        target_path = abs_target_path
        git_repo_dir = target_path

    # Change to the determined git repository directory
    try:
        os.chdir(git_repo_dir)
        print(f"Changed directory to: {git_repo_dir}")
    except FileNotFoundError:
        print(f"Error: Could not change to directory '{git_repo_dir}'. It might not exist.")
        sys.exit(1)


    if not os.path.exists(".git"):
        print(
            "Error: No .git directory found in the target path. Please initialize a Git repository first."
        )
        sys.exit(1)

    use_ai = not args.no_ai # Use AI by default, unless --no-ai is specified

    if is_single_file:
        # Commit a single file
        file_to_commit = target_path # target_path is already absolute
        
        # Check if file is ignored by .gitignore
        if is_file_ignored(file_to_commit):
            print(f"File {file_to_commit} is ignored by .gitignore, skipping.")
            return
        
        # Get the appropriate timestamp based on file status
        commit_datetime = get_appropriate_timestamp(file_to_commit)
        commit_date = commit_datetime.date()
        print(f"Committing single file: {file_to_commit} with date {commit_date}")
        
        commit_hash = None
        if use_ai:
            print("Attempting to generate commit message with AI...")
            commit_hash = commit_files([file_to_commit], commit_datetime, author_name, author_email, use_ai_for_message=True)
            if not commit_hash:
                # Fallback to non-AI message
                commit_hash = commit_files([file_to_commit], commit_datetime, author_name, author_email, use_ai_for_message=False)
        else:
            print("AI disabled, using default commit message.")
            commit_hash = commit_files([file_to_commit], commit_datetime, author_name, author_email, use_ai_for_message=False)

        if commit_hash:
            print(f"Single file commit successful: {commit_hash}")
        else:
            print("Single file commit failed after all attempts.")
    else: # It's a directory
        # Recursively find all files in the directory and collect their timestamps
        # target_path is the absolute path to the directory
        files_with_timestamps = []
        for root, _, files in os.walk(target_path):
            # Skip the .git directory and its contents
            if ".git" in root:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if file is ignored by .gitignore
                if is_file_ignored(file_path):
                    print(f"File {file_path} is ignored by .gitignore, skipping.")
                    continue
                
                # Get the appropriate timestamp based on file status
                commit_datetime = get_appropriate_timestamp(file_path)
                files_with_timestamps.append((file_path, commit_datetime))
        
        if not files_with_timestamps:
            print("No files found to commit in the specified directory and its subdirectories.")
            return

        # Sort files by timestamp (oldest first)
        files_with_timestamps.sort(key=lambda x: x[1])
        
        print(f"Found {len(files_with_timestamps)} files. Sorting by timestamp and committing in order.")

        successful_commits = 0
        failed_commits = 0
        for file_to_commit, commit_datetime in files_with_timestamps:
            commit_date = commit_datetime.date()
            print(f"\n--- Committing file: {file_to_commit} (Date: {commit_date}) ---")
            
            commit_hash = None
            if use_ai:
                print("Attempting to generate commit message with AI...")
                commit_hash = commit_files([file_to_commit], commit_datetime, author_name, author_email, use_ai_for_message=True)
                if not commit_hash:
                    # Fallback to non-AI message
                    commit_hash = commit_files([file_to_commit], commit_datetime, author_name, author_email, use_ai_for_message=False)
            else:
                print("AI disabled, using default commit message.")
                commit_hash = commit_files([file_to_commit], commit_datetime, author_name, author_email, use_ai_for_message=False)

            if commit_hash:
                print(f"Individual file commit successful: {commit_hash}")
                successful_commits += 1
            else:
                print(f"Individual file commit failed: {file_to_commit}")
                failed_commits += 1
        
        print("\n--- Directory Commit Summary ---")
        print(f"Successfully committed {successful_commits} files.")
        if failed_commits > 0:
            print(f"Failed to commit {failed_commits} files.")


if __name__ == "__main__":
    main()
