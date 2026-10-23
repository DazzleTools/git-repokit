# The licence catalogue: where each text came from, and its fingerprint

Source: `github/choosealicense.com`, `_licenses/<id>.txt`, commit `f66c5dd01866041688edd87f658b6d5ac3304f1b` (branch gh-pages, fetched 2026-10-23 by `tests/one-offs/thinking/p4-fetch-licenses/fetch.py`). Each file's YAML front matter was stripped and the placeholders `[year]`, `[yyyy]`, `[fullname]`, `[name of copyright owner]` became `__RK_YEAR__` and `__RK_HOLDER__`; nothing else changed. `all-rights-reserved.txt` is authored here, not fetched. The "or-later" variants (`gpl-3.0-or-later`, `lgpl-3.0-or-later`, `agpl-3.0-or-later`) are not files: `repokit.licenses` renders them from the base text with a notice line, because the licence text is identical and only the project's notice says "or later".

`tests/test_licenses.py` checks every shipped file against its shipped sha256; a changed file without a new row here fails.

| id | SPDX | title | sha256 as received | sha256 as shipped | tokens |
|---|---|---|---|---|---|
| 0bsd | 0BSD | BSD Zero Clause License | 749c160d5a8290da254f5fd02a510c6a234df5aea2f4f0711f309f2d9a821899 | e41dbf5f8aa40ed502ea4ab4023de21795d556d9a341734f2d24872dc4973d0c | holder, year |
| agpl-3.0 | AGPL-3.0 | GNU Affero General Public License v3.0 | 2a1fda78234b71502e2cf8035021b5592f5eba7e8107228aca4d95bba645e397 | 8486a10c4393cee1c25392769ddd3b2d6c242d6ec7928e1414efff7dfb2f07ef | none |
| apache-2.0 | Apache-2.0 | Apache License 2.0 | 609e2cb599f84aaa41d8ef29d8fdb04d164fab22e8d9292ca34a599d0f56a338 | 7ab3d1eca77d69cf60cb1e56379fa9a619b6fc300155904e1f8539ee6155e9c4 | holder, year |
| bsd-2-clause | BSD-2-Clause | BSD 2-Clause "Simplified" License | d8237d165c176416a8ab938bf7e120d8f345098163fcec9017c5652f467fecaf | fc29f42f5b8468afa3811a721ec1dd5c629f725e04785597ff4b7219887fe98e | holder, year |
| bsd-3-clause | BSD-3-Clause | BSD 3-Clause "New" or "Revised" License | 732e653d6b57d83ee9bd21ff53c6dd1eb332628cefd05df4b99d523727dff664 | f5d1fc68fbc06c286a11125154784b0b21fab066a1574a29f928f7c564ec8461 | holder, year |
| bsl-1.0 | BSL-1.0 | Boost Software License 1.0 | f8f6e066934a2365c12debd413b413caa0152791c87c0b16a12c8a65c3b92f9a | c9bff75738922193e67fa726fa225535870d2aa1059f91452c411736284ad566 | none |
| cc-by-4.0 | CC-BY-4.0 | Creative Commons Attribution 4.0 International | 736763bf08829e36266b8a3bebcc041ac68575424e976490671a7e6b43a525cf | f5b745ef98087f531e719ee8ca6a96809444573ecc7173c6fa68eaad39b3cc3f | none |
| cc-by-sa-4.0 | CC-BY-SA-4.0 | Creative Commons Attribution Share Alike 4.0 International | 8f85091fc554652d297119db8a092d8fc3d942ef3d768bd674decf48067a151f | 2003829cf643d61b00a76088dd31bb11b8029546f24c56b39fd492adb9281483 | none |
| cc0-1.0 | CC0-1.0 | Creative Commons Zero v1.0 Universal | db8278dfdfc1f73224f9f3762922c378344ca0443d36800baa61b3aaf31ef0e2 | a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499 | none |
| epl-2.0 | EPL-2.0 | Eclipse Public License 2.0 | 93c73b1678467af856e43dc4e7cc346991ab187b8da09b0e1a0cb010f6401ccd | 8c349f80764d0648e645f41ef23772a70c995a0924b5235f735f4a3d09df127c | none |
| gpl-2.0 | GPL-2.0 | GNU General Public License v2.0 | b7c21f2a2d0a1558458adbd90b9380d2514cebf970d12f26f84f862571c30ee2 | 8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643 | none |
| gpl-3.0 | GPL-3.0 | GNU General Public License v3.0 | e9c13804a52b8aea2e30033764d1b19f98369bae58028d9d1eb6b84e42b888bc | 3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986 | none |
| isc | ISC | ISC License | 8ea92c9e801b11e1303173c3ce3fc566bbe1ede96190aaffbc5a0c97712146c8 | 491a83f2c57434db8e97565ec680a129960783ef2c5c10d3c1b9734bf0b4ee79 | holder, year |
| lgpl-2.1 | LGPL-2.1 | GNU Lesser General Public License v2.1 | 0094ff7d2b4451d2231cd0c20b2798574c29bc81ef740d719a9909aabd86d633 | 20c17d8b8c48a600800dfd14f95d5cb9ff47066a9641ddeab48dc54aec96e331 | none |
| lgpl-3.0 | LGPL-3.0 | GNU Lesser General Public License v3.0 | 0b2e8a7c7a977908fa0bfaa2e2a7a54e3fd73676662e9fedae264db2916e0135 | e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118 | none |
| mit | MIT | MIT License | e6919db13cacb3300f918d1048d996d0f4506e1f110b7caa21f31ea7ca3ef5b8 | e3a0a9c39448343918a8bcbbf2dc5a0bce37cd0a937045ef6eeb869653fc0ec7 | holder, year |
| mpl-2.0 | MPL-2.0 | Mozilla Public License 2.0 | 0e03b8171b7b830a6a416b403eced17d39baed5b3a60563971f8b27aaa4f29e6 | 3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04 | none |
| unlicense | Unlicense | The Unlicense | ddc2e070df0bb25ce951b0954d9c1b5d22b17f150d58eac66bda653d044bb5ed | 6b0382b16279f26ff69014300541967a356a666eb0b91b422f6862f6b7dad17e | none |
| all-rights-reserved | LicenseRef-AllRightsReserved | All rights reserved (authored here) | - | 1025ba5f1f4d5a5583b50ea511aa986aa557b1a417ef92f52fe0696b4e5565c9 | holder, year |
