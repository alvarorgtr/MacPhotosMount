import os
import sys

from argparse import ArgumentParser
import stat
import errno
import trio
import pyfuse3
from pyfuse3 import Operations, FUSEError, ROOT_INODE

import faulthandler

from collection_utils import first
from library_info import PhotoLibrary

faulthandler.enable()


class PhotoFS(Operations):
    def __init__(self, library_path):
        super(PhotoFS, self).__init__()
        self.photo_library = PhotoLibrary(library_path)

    def __assign_inodes(self):
        self._inode_to_folder = {ROOT_INODE: self.photo_library.root_folder}
        self._folder_to_inode = {self.photo_library.root_folder: ROOT_INODE}
        for inode, folder in enumerate(self.photo_library.folders, start=ROOT_INODE + 1):
            if folder.parent:
                self._inode_to_folder[inode] = folder
                self._folder_to_inode[folder] = inode

        self._inode_to_asset = {}
        self._folder_asset_to_inode = {}
        inode = ROOT_INODE + len(self.photo_library.folders)
        for folder in self.photo_library.folders:
            for asset in folder.assets:
                self._inode_to_asset[inode] = asset
                self._folder_asset_to_inode[(folder, asset)] = inode
                inode += 1

    async def getattr(self, inode, ctx=None):
        entry = pyfuse3.EntryAttributes()
        if inode in self._inode_to_folder:
            # For a folder, we create our own stats
            entry.st_mode = (stat.S_IFDIR | 0o755)
            entry.st_size = 0   # Size of directory is system-defined

            # TODO: read times from the database and use them. For now, just use a hardcoded timestamp.
            stamp = int(1438467123.985654 * 1e9)
            entry.st_atime_ns = stamp
            entry.st_ctime_ns = stamp
            entry.st_mtime_ns = stamp

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

            for attr in ('st_nlink', 'st_uid', 'st_gid', 'st_rdev', 'st_size', 'st_atime_ns', 'st_mtime_ns', 'st_ctime_ns'):
                setattr(entry, attr, getattr(old_stat, attr))

            entry.generation = 0
            entry.entry_timeout = 0
            entry.attr_timeout = 0
            entry.st_blksize = 512
            entry.st_blocks = ((entry.st_size + entry.st_blksize - 1) // entry.st_blksize)
        else:
            raise FUSEError(errno.ENOENT)

        return entry

    async def lookup(self, parent_inode, name, ctx=None):
        name = os.fsdecode(name)
        folder = self._inode_to_folder[parent_inode]

        if not folder:
            raise FUSEError(errno.ENOENT)

        subfolder = first(lambda f: f.name == name, folder.children)
        if subfolder:
            inode = self._folder_to_inode[subfolder]
        elif name in folder.named_assets:
            asset = folder.named_assets[name]
            inode = self._folder_asset_to_inode[(folder, asset)]
        else:
            raise FUSEError(errno.ENOENT)

        return await self.getattr(inode)

    async def opendir(self, inode, ctx):
        if inode not in self._inode_to_folder:
            raise FUSEError(errno.ENOENT)

        return inode

    async def readdir(self, inode, offset, token):
        folder = self._inode_to_folder[inode]

        if folder:
            for i, subfolder in enumerate(folder.children[offset:]):
                inode = self._folder_to_inode[subfolder]
                attr = await self.getattr(inode)

                if not pyfuse3.readdir_reply(token, os.fsencode(subfolder.name), attr, i):
                    return

            offset = max(0, offset - len(folder.children))
            assets = sorted(folder.named_assets.items(), key=lambda item: item[0])
            for i, (name, asset) in enumerate(assets, len(folder.children))[offset:]:
                inode = self._folder_asset_to_inode[(folder, asset)]
                attr = await self.getattr(inode)

                if not pyfuse3.readdir_reply(token, os.fsencode(name), attr, i):
                    return

    async def open(self, inode, flags, ctx):
        if inode != self.hello_inode:
            raise FUSEError(errno.ENOENT)
        if flags & os.O_RDWR or flags & os.O_WRONLY:
            raise FUSEError(errno.EPERM)
        return pyfuse3.FileInfo(fh=inode)

    async def read(self, fh, off, size):
        assert fh == self.hello_inode
        return self.hello_data[off:off + size]


def init_logging(debug=False):
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(threadName)s: '
                                  '[%(name)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    if debug:
        handler.setLevel(logging.DEBUG)
        root_logger.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.INFO)
        root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


def parse_args():
    """Parse command line"""

    parser = ArgumentParser()

    parser.add_argument('mountpoint', type=str,
                        help='Where to mount the file system')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Enable debugging output')
    parser.add_argument('--debug-fuse', action='store_true', default=False,
                        help='Enable FUSE debugging output')
    return parser.parse_args()


def main():
    options = parse_args()
    init_logging(options.debug)

    testfs = TestFs()
    fuse_options = set(pyfuse3.default_options)
    fuse_options.add('fsname=hello')
    if options.debug_fuse:
        fuse_options.add('debug')
    pyfuse3.init(testfs, options.mountpoint, fuse_options)
    try:
        trio.run(pyfuse3.main)
    except:
        pyfuse3.close(unmount=False)
        raise

    pyfuse3.close()


if __name__ == '__main__':
    main()
