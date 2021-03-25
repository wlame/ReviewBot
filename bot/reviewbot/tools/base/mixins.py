"""Useful mixins for code checking tools.

Version Added:
    3.0
"""

from __future__ import unicode_literals

import logging
import os
import re

from reviewbot.utils.filesystem import chdir, ensure_dirs_exist


# Python 3.4+ includes glob.escape, but older versions do not. Optimistically,
# we'll use glob.escape, and we'll fall back on a custom implementation.
try:
    from glob import escape as glob_escape
except ImportError:
    _glob_escape_pattern = re.compile(r'([*?[])')

    def glob_escape(path):
        drive, path = os.path.split(path)

        return '%s%s' % (drive, _glob_escape_pattern.sub(r'[\1]', path))


class FilePatternsFromSettingMixin(object):
    """Mixin to set file patterns based on a configured tool setting.

    Subclasses can base file patterns off either a setting representing
    a comma-separated list of file patterns, or a setting representing a
    comma-separated list of file extensions. If both are provided, both will
    be checked, with the file patterns taking precedence over file extensions.

    If neither are provided by the user, the default list of file patterns
    set by the subclass (if any) will be used.

    Version Added:
        3.0
    """

    #: The name of a tool setting for a comma-separated list of extensions.
    #:
    #: Type:
    #:     unicode
    file_extensions_setting = None

    #: The name of a tool setting for a comma-separated list of patterns.
    #:
    #: Type:
    #:     unicode
    file_patterns_setting = None

    #: Whether to include default file patterns in the resulting list.
    #:
    #: Type:
    #:     boolean
    include_default_file_patterns = True

    def __init__(self, **kwargs):
        """Initialize the tool.

        Args:
            **kwargs (dict):
                Keyword arguments for the tool.
        """
        super(FilePatternsFromSettingMixin, self).__init__(**kwargs)

        split_re = re.compile(r'\s*,+\s*')

        settings = self.settings
        file_patterns = None

        if self.file_patterns_setting:
            value = settings.get(self.file_patterns_setting, '').strip()

            if value:
                file_patterns = split_re.split(value)

        if not file_patterns and self.file_extensions_setting:
            value = settings.get(self.file_extensions_setting, '').strip()

            if value:
                file_patterns = [
                    '*.%s' % glob_escape((ext.strip().lstrip('.')))
                    for ext in split_re.split(value)
                ]

        if file_patterns:
            if self.include_default_file_patterns and self.file_patterns:
                file_patterns += self.file_patterns

            self.file_patterns = [
                file_pattern
                for file_pattern in sorted(set(file_patterns))
                if file_pattern
            ]


class FullRepositoryToolMixin(object):
    """Mixin for tools that need access to the entire repository.

    This will take care of checking out a copy of the repository and applying
    patches from the diff being reviewed.

    Version Added:
        3.0:
        This replaced the legacy :py:class:`reviewbot.tools.RepositoryTool`.
    """

    working_directory_required = True

    def execute(self, review, repository=None, base_commit_id=None, **kwargs):
        """Perform a review using the tool.

        Args:
            review (reviewbot.processing.review.Review):
                The review object.

            settings (dict, optional):
                Tool-specific settings.

            repository (reviewbot.repositories.Repository, optional):
                The repository.

            base_commit_id (unicode, optional):
                The ID of the commit that the patch should be applied to.
        """
        repository.sync()
        working_dir = repository.checkout(base_commit_id)

        # Patch all the files first.
        with chdir(working_dir):
            for f in review.files:
                logging.info('Patching %s', f.dest_file)

                ensure_dirs_exist(os.path.abspath(f.dest_file))

                with open(f.dest_file, 'wb') as fp:
                    fp.write(f.patched_file_contents)

                f.patched_file_path = f.dest_file

            # Now run the tool for everything.
            super(FullRepositoryToolMixin, self).execute(review, **kwargs)
