import logging
import os
from argparse import ArgumentParser
import trio
import pyfuse3
import faulthandler

from library_info import PhotoLibrary
from photo_fs import PhotoFS

faulthandler.enable()


def parse_args():
    parser = ArgumentParser()

    parser.add_argument('photolibrary', type=str,
                        help='The .photoslibrary file to mount')
    parser.add_argument('mountpoint', type=str,
                        help='Where to mount the file system')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Enable debug logging')
    parser.add_argument('--fuse-debug', action='store_true', default=False,
                        help='Enable FUSE debug logging')
    return parser.parse_args()


def main():
    options = parse_args()

    # Build the photo library from the file
    library = PhotoLibrary(options.photolibrary)

    # Set the log level depending on the flags
    log_level = 'DEBUG' if options.debug else 'INFO'
    logging.basicConfig(level=os.environ.get('LOGLEVEL', log_level))

    print(f'Parsed photo library with {len(library.assets)} unique assets')

    print(f'Mounting photo library to {options.mountpoint}...')

    # Create and run the file system
    filesystem = PhotoFS(library)
    fuse_options = set(pyfuse3.default_options)
    fuse_options.add('fsname=PhotoLibrary')

    # Set up fuse debugging if requested
    if options.fuse_debug:
        fuse_options.add('debug')

    pyfuse3.init(filesystem, options.mountpoint, fuse_options)

    print('Mounted!')

    try:
        trio.run(pyfuse3.main)
    except:
        pyfuse3.close(unmount=False)
        raise

    pyfuse3.close()
    print('Unmounted filesystem')


if __name__ == '__main__':
    main()
