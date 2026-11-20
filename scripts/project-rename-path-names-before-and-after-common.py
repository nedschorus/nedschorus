"""The path renames of the project rename's stage 3, in both directions: the one list that the rename's rewrite program
moves files by and that code reading paths written before the rename reads them through.

A directory named by a key of DIRECTORY_NAMES_BY_NAME_BEFORE_PROJECT_RENAME gets its value as its name. Any other
directory or file whose name starts with a key of FILE_AND_DIRECTORY_NAME_PREFIXES_BY_PREFIX_BEFORE_PROJECT_RENAME gets that key's value
in place of the prefix.
"""

# The rename's rewrite program leaves a line that assigns a name ending _BEFORE_PROJECT_RENAME alone, so these lines
# keep the old names.
DIRECTORY_NAMES_BY_NAME_BEFORE_PROJECT_RENAME = {"nc-systems": "nn-systems", "nc-queue": "nn-queue"}
FILE_AND_DIRECTORY_NAME_PREFIXES_BY_PREFIX_BEFORE_PROJECT_RENAME = {"nc-shared-database": "nn-shared-database", "nedschorus-": "nedsnodes-"}


def _renamed_part(part, directory_names, name_prefixes):
    if part in directory_names:
        return directory_names[part]
    for prefix, new_prefix in name_prefixes.items():
        if part.startswith(prefix):
            return new_prefix + part[len(prefix):]
    return part


def convert_file_path_before_project_rename_to_path_after(path):
    """The path a path written before the project rename has now; a path the rename did not move comes back as it is."""
    return "/".join(_renamed_part(part, DIRECTORY_NAMES_BY_NAME_BEFORE_PROJECT_RENAME,
                                  FILE_AND_DIRECTORY_NAME_PREFIXES_BY_PREFIX_BEFORE_PROJECT_RENAME) for part in path.split("/"))


def convert_file_path_after_project_rename_to_path_before(path):
    """The path a path had before the project rename; a path the rename did not move comes back as it is."""
    return "/".join(_renamed_part(part, {new: old for old, new in DIRECTORY_NAMES_BY_NAME_BEFORE_PROJECT_RENAME.items()},
                                  {new: old for old, new in FILE_AND_DIRECTORY_NAME_PREFIXES_BY_PREFIX_BEFORE_PROJECT_RENAME.items()})
                    for part in path.split("/"))
