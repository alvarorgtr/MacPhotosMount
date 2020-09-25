For a .photoslibrary file...

- The database is in database/Photos.sqlite (metaSchema.db and photos.db are deprecated).
- The files are in originals, inside 16 subfolders named from 0 to F, and with an UUID as name.
- There is a similar file structure in resources/derivatives, with a particular naming scheme.

The database table pointing to the file names is ZGENERICASSET, the data can be obtained with:

```sql
SELECT Z_PK, Z_ENT, Z_OPT, ZDIRECTORY, ZFILENAME
FROM ZGENERICASSET;
```