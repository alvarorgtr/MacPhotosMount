'''
Inspired on the pyfuse3 examples.
'''

import errno
import logging
import os
import stat
import pyfuse3

from pyfuse3 import Operations, FUSEError, ROOT_INODE

from collection_utils import first
from library_info import PhotoLibrary

logger = logging.getLogger(__name__)


class PhotoFS(Operations):
    def __init__(self, photo_library):
        super(PhotoFS, self).__init__()
        self.photo_library = photo_library
        self.__assign_inodes()

    def __assign_inodes(self):
        self._inode_to_folder = {ROOT_INODE: self.photo_library.root_folder}
        self._folder_to_inode = {self.photo_library.root_folder: ROOT_INODE}
        for inode, folder in enumerate(filter(lambda f: f.parent, self.photo_library.folders), start=ROOT_INODE + 1):
            self._inode_to_folder[inode] = folder
            self._folder_to_inode[folder] = inode

        logger.debug(f'Assigned inodes to {len(self._inode_to_folder)} folders')

        self._inode_to_asset = {}
        self._folder_asset_to_inode = {}
        inode = ROOT_INODE + len(self.photo_library.folders)
        for folder in self.photo_library.folders:
            for asset in folder.assets:
                self._inode_to_asset[inode] = asset
                self._folder_asset_to_inode[(folder, asset)] = inode
                inode += 1

        logger.debug(f'Assigned inodes to {len(self._inode_to_asset)} assets')

        self._inode_to_fd = {}
        self._fd_to_inode = {}
        self._fd_to_open_count = {}

    async def getattr(self, inode, ctx=None):
        logger.debug(f'getattr() called for inode {inode}')

        entry = pyfuse3.EntryAttributes()
        if inode in self._inode_to_folder:
            folder = self._inode_to_folder[inode]

            # For a folder, we create our own stats
            entry.st_mode = (stat.S_IFDIR | 0o755)
            entry.st_size = 0   # Size of directory is system-defined

            entry.generation = 0
            entry.entry_timeout = 0
            entry.attr_timeout = 0

            # TODO: atime is not real
            entry.st_atime_ns = folder.creation_epoch * 1_000_000_000
            entry.st_ctime_ns = folder.creation_epoch * 1_000_000_000
            entry.st_mtime_ns = folder.creation_epoch * 1_000_000_000

            entry.st_gid = os.getgid()
            entry.st_uid = os.getuid()
            entry.st_ino = inode
        elif inode in self._inode_to_asset:
            # This is an asset, we have a file to base all this information on
            asset = self._inode_to_asset[inode]
            asset_path = asset.original_path(self.photo_library.path)

            try:
                old_stat = os.lstat(asset_path)
            except OSError as exc:
                raise FUSEError(exc.errno)

            # Select the most restrictive mode between readonly and the original file's
            entry.st_mode = (stat.S_IFREG | (0o644 & old_stat.st_mode))
            entry.st_ino = inode

            for attr in ('st_nlink', 'st_uid', 'st_gid', 'st_rdev', 'st_size'):
                setattr(entry, attr, getattr(old_stat, attr))

            # TODO: atime is not real
            entry.st_atime_ns = asset.added_epoch * 1_000_000_000
            entry.st_ctime_ns = asset.creation_epoch * 1_000_000_000
            entry.st_mtime_ns = asset.creation_epoch * 1_000_000_000

            entry.generation = 0
            entry.entry_timeout = 0
            entry.attr_timeout = 0

            entry.st_blksize = 512
            entry.st_blocks = ((entry.st_size + entry.st_blksize - 1) // entry.st_blksize)
        else:
            raise FUSEError(errno.ENOENT)

        return entry

    async def lookup(self, parent_inode, name, ctx=None):
        logger.debug(f'Lookup() called for parent inode {parent_inode}, name {name}')

        name = os.fsdecode(name)
        folder = self._inode_to_folder[parent_inode]

        if not folder:
            raise FUSEError(errno.ENOENT)

        subfolder = first(lambda f: f.name == name, folder.children)
        if name == '.':
            inode = parent_inode
            logger.debug(f'lookup found folder \'.\' with inode {inode}')
        elif name == '.':
            inode = self._folder_to_inode[folder.parent]
            logger.debug(f'lookup found folder \'..\' with inode {inode}')
        elif subfolder:
            inode = self._folder_to_inode[subfolder]
            logger.debug(f'lookup found subfolder with inode {inode}')
        elif name in folder.named_assets:
            asset = folder.named_assets[name]
            inode = self._folder_asset_to_inode[(folder, asset)]
            logger.debug(f'lookup found asset with inode {inode}')
        else:
            raise FUSEError(errno.ENOENT)

        return await self.getattr(inode)

    async def opendir(self, inode, ctx):
        logger.debug(f'opendir() called for inode {inode}')

        if inode not in self._inode_to_folder:
            raise FUSEError(errno.ENOENT)

        return inode

    async def readdir(self, dir_inode, offset, token):
        folder = self._inode_to_folder[dir_inode]

        logger.debug(f'readdir() called for inode {dir_inode} (folder {folder.name}), offset {offset}, token {token}')

        offset += 1

        if folder:
            for i, subfolder in enumerate(folder.children[offset:], offset):
                inode = self._folder_to_inode[subfolder]
                attr = await self.getattr(inode)

                logger.debug(f'Contents: {dir_inode}[{i}] = {inode} (folder {subfolder.name})')
                if not pyfuse3.readdir_reply(token, os.fsencode(subfolder.name), attr, i):
                    return

            offset = max(0, offset - len(folder.children))
            assets = folder.sorted_named_assets[offset:]
            for i, (name, asset) in enumerate(assets, len(folder.children) + offset):
                inode = self._folder_asset_to_inode[(folder, asset)]
                attr = await self.getattr(inode)

                logger.debug(f'Contents: {dir_inode}[{i}] = {inode} (asset {asset.id})')
                if not pyfuse3.readdir_reply(token, os.fsencode(name), attr, i):
                    return
        else:
            raise FUSEError(errno.ENOENT)

    async def open(self, inode, flags, ctx):
        logger.debug(f'open() called for inode {inode}')

        if inode in self._inode_to_fd:
            fd = self._inode_to_fd[inode]
            self._fd_to_open_count[fd] += 1
            return pyfuse3.FileInfo(fh=fd)
        else:
            asset = self._inode_to_asset[inode]
            if not asset:
                raise FUSEError(errno.ENOENT)

            try:
                fd = os.open(asset.original_path(self.photo_library.path), flags)
            except OSError as err:
                raise FUSEError(err.errno)

            self._inode_to_fd[inode] = fd
            self._fd_to_inode[fd] = inode
            self._fd_to_open_count[fd] = 1

            return pyfuse3.FileInfo(fh=fd)

    async def read(self, fd, offset, size):
        logger.debug(f'read() called for file descriptor {fd}')

        os.lseek(fd, offset, os.SEEK_SET)
        return os.read(fd, size)
