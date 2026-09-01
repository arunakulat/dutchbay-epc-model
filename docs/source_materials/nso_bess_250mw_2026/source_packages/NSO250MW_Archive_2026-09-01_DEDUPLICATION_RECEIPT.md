# NSO 250 MW OEM archive re-supply - deduplication receipt

## Source package

| Field | Receipt |
|---|---|
| Received | 1 September 2026 |
| Supplied filename | `Archive.zip` |
| Archive size | 25,984,565 bytes |
| Archive SHA-256 | `8aefe0e6a3ea967055e52740a37c7ea1a39f60d98726bb604dbc8a8b4ee46ef2` |
| ZIP integrity | Pass; every central-directory member decompressed without error |
| Path safety | No absolute path, parent traversal, backslash path, symlink or encrypted member |
| Central-directory entries | 122 |
| Payload files | 50 instances; 33,968,065 uncompressed bytes |
| Finder metadata | 63 metadata files plus 9 directory entries; excluded from the corpus |
| Unique payload SHA-256 values | 48 |
| New payload values versus the live corpus | 0 |

The archive was unpacked into a controlled temporary directory. Every payload file was hashed and
compared by content with all files under `docs/source_materials/nso_bess_250mw_2026/`. All 50
instances matched an existing canonical file byte-for-byte. The temporary extraction was then
removed. No archive payload was copied into the corpus a second time. The complete member-level
mapping, including the source path, hash, size, duplicate-instance status and canonical corpus
path, is retained in `NSO250MW_Archive_2026-09-01.DEDUPLICATION.csv`.

## Intra-archive duplicate groups

| SHA-256 | Source members | Canonical corpus object |
|---|---|---|
| `8f1f0a8bff28982d271f3d5d08646d85186dea3cd9fceb49a08e28aa364136e4` | `21. PSS®E  and  PSCAD/6.04b ... Electrical Primary Diagram ... V2.1.pdf`; `20. Envision Energy_Electrical Primary Diagram ... V2.1.pdf` | `../oem/envision/product_docs/20_Envision_Electrical_Primary_Diagram_ENS-D6G-24120-10100-000_0.25P4h_V2.1.pdf` |
| `7585c0adbc197791fe813e538f18e89145b69ab68375a9450a2b96a3b0f85b69` | AC-side and DC-side copies of `Standards Compliance List.xlsx` | `../oem/envision/compliance_evidence/Standards_Compliance_List.xlsx` |

## Loose-file re-check requested 1 September 2026

The eleven separately supplied loose files have eleven different hashes from one another, but none
is new to the corpus. Each source hash and size matches the listed canonical object exactly.

| Supplied file | SHA-256 | Corpus history |
|---|---|---|
| `25. Envision Energy_Contract Spare Parts List Tool V2.0.pdf` | `0bd3f9dc91c3a2d77a0a2733b6bba6eebf27f83a6f28afead1452a8ea159539a` | Added by `0e63f7a` / PR #1181, the 27 August tranche merged 29 August |
| `16. Details of auxiliary Power consumption during charging, discharging and idle.txt` | `2a3c236c83bc86ca237ff38297f7ab2012d84274a06d2f05b23a5bf064659e7d` | Added by `0e63f7a` / PR #1181; the corpus also has a byte-identical discovery-aid copy under `extracted/` |
| `Sri Lanka 11MW_44MWh.pdf` | `0cf77ec5d7615c611e0a5cbbf7ab8c3f8a6a722e5b31e42a25fad27f88841e86` | Added earlier by `4d8f6d0` / PR #1029 on 16 August; re-supplied, not originated, in the later pack |
| `12. Envision BESS Sales Track Record_2026.8.25.pdf` | `bab6d1ee4511a3af4c995bd3c83fd0bf32266252e8ab44d7f7c813b3c0b55eb8` | Added by `0e63f7a` / PR #1181 |
| `1. Technical Specifications.pdf` | `d535d7f0da16dc3d9cef099fb51503e5b436aee14e60fddab050141db140809b` | Added by `0e63f7a` / PR #1181 |
| `23. LTSA Solution.xlsx` | `53a51d5c3c9cf91763f01b35086bb1bf2e97ba4357a0265d7b26223547be4123` | Added by `0e63f7a` / PR #1181 |
| `7. Envision Energy_Fire Protection System Specification of ENS-D_V2.0.pdf` | `868006ff98e4af7ef47609dadf6855d5990663c3170a9a560b0476d458b9892d` | Added by `0e63f7a` / PR #1181 |
| `15. Envision BESS Maintenance Technical Description_ENS-D Series_V1.0.pdf` | `578be8f708458d01417d2f6845b2797a14fd4fb80d571e5d2dfb85641520121f` | Added by `0e63f7a` / PR #1181 |
| `17. Envision Energy_BESS Dismantling Technical Description 10MWh_V2.0.pdf` | `91d62a381e91334825dd6c8484d33ef9e66be035cef15fc1bf699d35e53d06ad` | Added by `0e63f7a` / PR #1181 |
| `9. Envision Energy_Layout Instruction of  BESS System__ENS-D Seires V1.0.pdf` | `62af9a2c395003cf14d1c2bb11979931ca0a74d7f64ef5f19cc1426f61f9d910` | Added by `0e63f7a` / PR #1181 |
| `18. Envision Energy_Recommended Foundation of ENS-D Series V1.1.pdf` | `ba702fe2093d2968edf0af0329b3010d413a78847891370b47fa23e3c9d17cff` | Added by `0e63f7a` / PR #1181 |

The exact canonical hashes for the OEM tranche remain in
`NSO250MW_oem_supply_2026-08-27.MANIFEST.sha256`; the complete corpus is pinned by
`../MANIFEST.sha256`. This receipt adds outer-package provenance only. It does not change the
technical interpretation, compliance status or release status of any member.
