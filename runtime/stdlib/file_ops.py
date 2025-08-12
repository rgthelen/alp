"""File system operations for ALP."""
import os
import glob as glob_module
import shutil
from pathlib import Path
import json

def register(reg):
    def _get_safe_path(path_str):
        """Ensure path is under ALP_IO_ROOT."""
        root = os.getenv("ALP_IO_ROOT", os.getcwd())
        full_path = os.path.abspath(os.path.join(root, path_str))
        if not full_path.startswith(os.path.abspath(root)):
            raise RuntimeError(f"Path escapes sandbox: {path_str}")
        return full_path
    
    def list_files(a, ctx):
        """List files in a directory.
        
        Args:
            path: Directory path (default: current)
            pattern: Optional glob pattern filter
            recursive: Include subdirectories
            type: Filter by type (file, dir, all)
            
        Returns:
            List of file paths
        """
        path = a.get("path", ".")
        pattern = a.get("pattern", "*")
        recursive = a.get("recursive", False)
        file_type = a.get("type", "all")
        
        try:
            safe_path = _get_safe_path(path)
            
            if recursive:
                full_pattern = os.path.join(safe_path, "**", pattern)
                paths = glob_module.glob(full_pattern, recursive=True)
            else:
                full_pattern = os.path.join(safe_path, pattern)
                paths = glob_module.glob(full_pattern)
            
            # Filter by type
            result = []
            for p in paths:
                if file_type == "file" and os.path.isfile(p):
                    result.append(os.path.relpath(p, safe_path))
                elif file_type == "dir" and os.path.isdir(p):
                    result.append(os.path.relpath(p, safe_path))
                elif file_type == "all":
                    result.append(os.path.relpath(p, safe_path))
            
            return {"files": result, "count": len(result)}
        except Exception as e:
            return {"files": [], "count": 0, "error": str(e)}
    
    def file_exists(a, ctx):
        """Check if a file or directory exists.
        
        Args:
            path: Path to check
            
        Returns:
            Existence and type information
        """
        path = a.get("path", "")
        
        try:
            safe_path = _get_safe_path(path)
            exists = os.path.exists(safe_path)
            
            if exists:
                is_file = os.path.isfile(safe_path)
                is_dir = os.path.isdir(safe_path)
                return {
                    "exists": True,
                    "type": "file" if is_file else "dir" if is_dir else "other",
                    "path": path
                }
            else:
                return {"exists": False, "path": path}
        except Exception as e:
            return {"exists": False, "path": path, "error": str(e)}
    
    def glob(a, ctx):
        """Find files matching a pattern.
        
        Args:
            pattern: Glob pattern (e.g., "*.txt", "**/*.py")
            root: Root directory (default: current)
            recursive: Enable ** for recursive matching
            
        Returns:
            List of matching paths
        """
        pattern = a.get("pattern", "*")
        root = a.get("root", ".")
        recursive = a.get("recursive", "**" in pattern)
        
        try:
            safe_root = _get_safe_path(root)
            full_pattern = os.path.join(safe_root, pattern)
            
            matches = glob_module.glob(full_pattern, recursive=recursive)
            
            # Return relative paths
            result = [os.path.relpath(m, safe_root) for m in matches]
            
            return {"matches": result, "count": len(result)}
        except Exception as e:
            return {"matches": [], "count": 0, "error": str(e)}
    
    def file_info(a, ctx):
        """Get detailed information about a file.
        
        Args:
            path: File path
            
        Returns:
            File metadata
        """
        path = a.get("path", "")
        
        try:
            safe_path = _get_safe_path(path)
            
            if not os.path.exists(safe_path):
                return {"exists": False, "path": path}
            
            stat = os.stat(safe_path)
            
            return {
                "exists": True,
                "path": path,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "is_file": os.path.isfile(safe_path),
                "is_dir": os.path.isdir(safe_path),
                "readable": os.access(safe_path, os.R_OK),
                "writable": os.access(safe_path, os.W_OK),
                "extension": os.path.splitext(path)[1]
            }
        except Exception as e:
            return {"exists": False, "path": path, "error": str(e)}
    
    def mkdir(a, ctx):
        """Create a directory.
        
        Args:
            path: Directory path
            parents: Create parent directories if needed
            exist_ok: Don't error if already exists
            
        Returns:
            Creation status
        """
        if os.getenv("ALP_IO_ALLOW_WRITE", "0") not in ("1", "true", "yes"):
            return {"created": False, "error": "Write operations disabled"}
        
        path = a.get("path", "")
        parents = a.get("parents", True)
        exist_ok = a.get("exist_ok", True)
        
        try:
            safe_path = _get_safe_path(path)
            
            if parents:
                os.makedirs(safe_path, exist_ok=exist_ok)
            else:
                os.mkdir(safe_path)
            
            return {"created": True, "path": path}
        except FileExistsError:
            if exist_ok:
                return {"created": False, "path": path, "existed": True}
            else:
                return {"created": False, "path": path, "error": "Directory already exists"}
        except Exception as e:
            return {"created": False, "path": path, "error": str(e)}
    
    def copy_file(a, ctx):
        """Copy a file or directory.
        
        Args:
            source: Source path
            destination: Destination path
            overwrite: Overwrite if destination exists
            
        Returns:
            Copy status
        """
        if os.getenv("ALP_IO_ALLOW_WRITE", "0") not in ("1", "true", "yes"):
            return {"copied": False, "error": "Write operations disabled"}
        
        source = a.get("source", "")
        destination = a.get("destination", "")
        overwrite = a.get("overwrite", False)
        
        try:
            safe_source = _get_safe_path(source)
            safe_dest = _get_safe_path(destination)
            
            if not os.path.exists(safe_source):
                return {"copied": False, "error": "Source does not exist"}
            
            if os.path.exists(safe_dest) and not overwrite:
                return {"copied": False, "error": "Destination already exists"}
            
            if os.path.isfile(safe_source):
                shutil.copy2(safe_source, safe_dest)
            else:
                shutil.copytree(safe_source, safe_dest, dirs_exist_ok=overwrite)
            
            return {"copied": True, "source": source, "destination": destination}
        except Exception as e:
            return {"copied": False, "error": str(e)}
    
    def move_file(a, ctx):
        """Move/rename a file or directory.
        
        Args:
            source: Source path
            destination: Destination path
            overwrite: Overwrite if destination exists
            
        Returns:
            Move status
        """
        if os.getenv("ALP_IO_ALLOW_WRITE", "0") not in ("1", "true", "yes"):
            return {"moved": False, "error": "Write operations disabled"}
        
        source = a.get("source", "")
        destination = a.get("destination", "")
        overwrite = a.get("overwrite", False)
        
        try:
            safe_source = _get_safe_path(source)
            safe_dest = _get_safe_path(destination)
            
            if not os.path.exists(safe_source):
                return {"moved": False, "error": "Source does not exist"}
            
            if os.path.exists(safe_dest) and not overwrite:
                return {"moved": False, "error": "Destination already exists"}
            
            shutil.move(safe_source, safe_dest)
            
            return {"moved": True, "source": source, "destination": destination}
        except Exception as e:
            return {"moved": False, "error": str(e)}
    
    def delete_file(a, ctx):
        """Delete a file or directory.
        
        Args:
            path: Path to delete
            recursive: Delete directories recursively
            
        Returns:
            Deletion status
        """
        if os.getenv("ALP_IO_ALLOW_WRITE", "0") not in ("1", "true", "yes"):
            return {"deleted": False, "error": "Write operations disabled"}
        
        path = a.get("path", "")
        recursive = a.get("recursive", False)
        
        try:
            safe_path = _get_safe_path(path)
            
            if not os.path.exists(safe_path):
                return {"deleted": False, "error": "Path does not exist"}
            
            if os.path.isfile(safe_path):
                os.remove(safe_path)
            elif os.path.isdir(safe_path):
                if recursive:
                    shutil.rmtree(safe_path)
                else:
                    os.rmdir(safe_path)
            
            return {"deleted": True, "path": path}
        except Exception as e:
            return {"deleted": False, "path": path, "error": str(e)}
    
    def path_join(a, ctx):
        """Join path components.
        
        Args:
            parts: List of path parts to join
            
        Returns:
            Joined path
        """
        parts = a.get("parts", [])
        
        if not parts:
            return {"path": ""}
        
        result = os.path.join(*[str(p) for p in parts])
        return {"path": result}
    
    def path_split(a, ctx):
        """Split a path into components.
        
        Args:
            path: Path to split
            
        Returns:
            Path components
        """
        path = a.get("path", "")
        
        dirname, basename = os.path.split(path)
        name, ext = os.path.splitext(basename)
        
        return {
            "dir": dirname,
            "base": basename,
            "name": name,
            "ext": ext,
            "parts": path.split(os.sep) if path else []
        }
    
    reg("list_files", list_files)
    reg("file_exists", file_exists)
    reg("glob", glob)
    reg("file_info", file_info)
    reg("mkdir", mkdir)
    reg("copy_file", copy_file)
    reg("move_file", move_file)
    reg("delete_file", delete_file)
    reg("path_join", path_join)
    reg("path_split", path_split)