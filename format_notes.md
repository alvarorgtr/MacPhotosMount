For a .photoslibrary file...

- The database is in database/Photos.sqlite (metaSchema.db and photos.db are deprecated).
- The files are in originals, inside 16 subfolders named from 0 to F, and with an UUID as name.
- There is a similar file structure in resources/derivatives, with a particular naming scheme.

The database table pointing to the file names is ZGENERICASSET, the data can be obtained with:

```sql
SELECT Z_PK, Z_ENT, Z_OPT, ZDIRECTORY, ZFILENAME
FROM ZGENERICASSET;
```

ZGENERICALBUM has album information, but names are not there...

Tables named Z_<two digits>NAME. Hypothesis: those are relationship tables. The two digits seem to come from this table:

```sql
SELECT * FROM Z_PRIMARYKEY;
```

```
Z_ENT (integer) | Z_NAME (varchar), Z_SUPER (integer), Z_MAX (integer)
1|AdditionalAssetAttributes|0|6693
2|Adjustment|0|0
3|AlbumList|0|7
4|AssetAnalysisState|0|6693
5|AssetDescription|0|59
6|CloudFeedEntry|0|0
7|CloudFeedAssetsEntry|6|0
8|CloudFeedCommentsEntry|6|0
9|CloudMaster|0|0
10|CloudMasterMediaMetadata|0|0
11|CloudResource|0|0
12|CloudSharedAlbumInvitationRecord|0|0
13|CloudSharedComment|0|0
14|Codec|0|1
15|ComputedAssetAttributes|0|6606
16|DeferredRebuildFace|0|0
17|DetectedFace|0|1157911
18|DetectedFaceGroup|0|4925
19|DetectedFaceprint|0|19156
20|EditedIPTCAttributes|0|130
21|ExtendedAttributes|0|6693
22|FaceCrop|0|124
23|FileSystemBookmark|0|0
24|FileSystemVolume|0|0
25|GenericAlbum|0|1465
26|Album|25|0
27|CloudSharedAlbum|26|0
28|LegacyFaceAlbum|26|0
29|PhotoStreamAlbum|26|0
30|ProjectAlbum|26|0
31|FetchingAlbum|25|0
32|Folder|25|0
33|ImportSession|25|0
34|GenericAsset|0|6693
35|Asset|34|0
36|InternalResource|0|13605
37|Keyword|0|11
38|LegacyFace|0|0
39|MediaAnalysisAssetAttributes|0|6689
40|Memory|0|97
41|Moment|0|704
42|MomentList|0|114
43|MomentShare|0|0
44|MomentShareParticipant|0|0
45|Person|0|5017
46|PersonReference|0|0
47|PhotosHighlight|0|765
48|SceneClassification|0|180674
49|Sceneprint|0|6602
50|SearchData|0|0
51|Suggestion|0|0
52|UniformTypeIdentifier|0|11
53|UnmanagedAdjustment|0|77
16001|CHANGE|0|309854
16002|TRANSACTION|0|17318
16003|TRANSACTIONSTRING|0|966
```

In that case, Z_25ALBUMLISTS and Z_26ASSETS are interesting.

Album lists are defined in ZALBUMLIST.
Assets look to be defined in ZGENERICASSET.
It looks like Z_26ASSETS matches albums by their PK IN ZGENERICALBUM with assets by their PK in ZGENERICASSET.
The main folders seem to have Z_PK = 2 as a parent.