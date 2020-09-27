import os
from contextlib import closing
import sqlite3

from collection_utils import dict_grouping


class SQLiteLoader:
    def __init__(self, db_path):
        self.db_path = db_path

    def __select(self, query):
        with closing(sqlite3.connect(self.db_path)) as con, closing(con.cursor()) as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    def all_assets(self):
        assets_query = """
        SELECT Z_PK, ZDIRECTORY, ZFILENAME
        FROM ZGENERICASSET
        WHERE Z_ENT = 35;
        """

        return list(map(Asset.from_row, self.__select(assets_query)))

    def all_folders(self):
        folders_query = """
        WITH RECURSIVE
        album_hierarchy(pk, level, isleaf) AS
            (SELECT z_pk, 0, 0 FROM zgenericalbum WHERE z_ent = 32 AND zkind = 3999
            UNION ALL
            SELECT z_pk, h.level + 1, CASE WHEN g.z_ent = 26 THEN 1 ELSE 0 END
            FROM zgenericalbum g JOIN album_hierarchy h ON g.zparentfolder = h.pk
            WHERE (g.z_ent = 32 AND g.zkind = 4000) OR (g.z_ent = 26 AND g.zkind = 2))
        SELECT z_pk, z_ent, zparentfolder, ztitle, h.level, h.isleaf
        FROM zgenericalbum g JOIN album_hierarchy h ON g.z_pk = h.pk;
        """
        return list(map(Folder.from_row, self.__select(folders_query)))

    def folder_asset_relationship(self):
        relationship_query = """
        SELECT z_26albums, z_34assets
        FROM z_26assets rel JOIN zgenericalbum al ON rel.z_26albums = al.z_pk
        WHERE al.zkind = 2;
        """

        return list(self.__select(relationship_query))


class Asset:
    def __init__(self, id, directory, file_name):
        self.id = id
        self.directory = directory
        self.file_name = file_name

    @staticmethod
    def from_row(row):
        return Asset(row[0], row[1], row[2])

    def original_path(self, library_path):
        return os.path.join(library_path, 'originals', self.directory, self.file_name)


class Folder:
    def __init__(self, id, parent_id, name, level):
        self.id = id
        self.parent_id = parent_id
        self.name = name
        self.level = level
        self.assets = []
        self.children = []

    @staticmethod
    def from_row(row):
        return Folder(row[0], row[2], row[3], row[4])

    def add_child(self, child):
        self.children.append(child)

    def __repr__(self):
        return f'Folder(id: {self.id}, name: {self.name})'

    def __eq__(self, other):
        return self.id == other.id


class PhotoLibrary:
    def __init__(self, path):
        self.path = path
        self.__load()

    def __load(self):
        db_path = os.path.join(self.path, 'database', 'Photos.sqlite')
        loader = SQLiteLoader(db_path)
        folders = loader.all_folders()
        assets = loader.all_assets()
        relationship = loader.folder_asset_relationship()

        self.root_folder = self.__build_folder_hierarchy(folders, assets, relationship)

    @staticmethod
    def __build_folder_hierarchy(folders, assets, relationship):
        # TODO: we assume for now that only one root folder will exist.
        root = next(filter(lambda folder: folder.level == 0, folders), None)

        if not root:
            raise ValueError('No root folder found')

        folder_map = dict_grouping(lambda f: f.id, folders)

        # Add every folder to their parent
        for folder in folders:
            # Skip the root folder
            if folder.parent_id:
                # The parent will always exist because we have made sure of that with the query
                parent = folder_map[folder.parent_id]
                parent.children.append(folder)

        # Now, add every asset to their folder
        asset_map = dict_grouping(lambda f: f.id, assets)
        for folder_id, asset_id in relationship:
            asset = asset_map[asset_id]
            folder = folder_map[folder_id]
            folder.assets.append(asset)

        return root
    