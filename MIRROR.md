# Removed from this mirror

A scanner-clean mirror of flutter/flutter's `stable` branch and its release tags.
Every blob a malware, secret or archive scanner may refuse was removed from every
commit (`git filter-repo --strip-blobs-with-ids`); the rest of the history is upstream's.

- upstream `stable` commit: `c197ca5199e9ee5661e865596c9c07294dfab51c`
- mirror `stable` commit: `255b2d07cc58470e63547816d77d0a4d04357b42`
- tags: 711
- blobs scanned in the result: 366659
- blobs removed: 36

A removed blob is absent from all commits that held it, under whatever path. The
path shown is one place it was seen. Tests that read these fixtures fail.

## Using `master`

`master` has no `bin/internal/engine.version`: the tool computes the engine version as a
hash of the `DEPS` and `engine` tree ids. Removing blobs under `engine/` changes that
tree, so the mirror's own hash names no published engine. Set the upstream's:

- upstream hash for this master: `3f1e20a900d3040be55428ba7fe01aa07290a1e3` (engine artifacts published: yes)
- mirror's computed hash (no artifacts): `cb3e1dc6b72c83bb15f9667faf23130c38d6a79d`
- `FLUTTER_PREBUILT_ENGINE_VERSION=3f1e20a900d3040be55428ba7fe01aa07290a1e3`

`stable` and the tags carry `engine.version`, which the rewrite leaves unchanged.

## der (certificate or key) (1)

| blob | bytes | path |
| --- | ---: | --- |
| `df0714f9b96d27c4abac51776c167e1919d81e71` | 2618 | `engine/src/flutter/testing/android/native_activity/debug.keystore` |

## key or keystore file (2)

| blob | bytes | path |
| --- | ---: | --- |
| `67eb0aa34c5af88603ee1e2dedf4bfee3e33be2c` | 2223 | `engine/src/flutter/build/android/ant/chromium-debug.keystore` |
| `844d15087194eafd581c52a0bd3dd291c0143e2f` | 64 | `engine/src/flutter/tools/fuchsia/development.key` |

## mach-o/java class (1)

| blob | bytes | path |
| --- | ---: | --- |
| `878bf4c514f437be4e85dec03fa21b8a6d485e09` | 6070016 | `dev/integration_tests/ios_add2app/Pods/EarlGrey/EarlGrey/EarlGrey.framework/EarlGrey` |

## opaque high-entropy data (2)

| blob | bytes | path |
| --- | ---: | --- |
| `b9972711e73226c83586fa232c6e71853fe7f451` | 2067 | `dev/bots/serviceaccount.enc` |
| `934fb54d328c594048446a9b56668db471fb5bbf` | 422738 | `examples/game/assets/temp_music.aac` |

## private key in text (26)

| blob | bytes | path |
| --- | ---: | --- |
| `37893b84fc11c25cb5dddee9bdd202aa0d90a462` | 1628 | `engine/src/flutter/tests/http/conf/webkit-httpd.pem` |
| `9c0b4bf95e33626c181ea0c63f533eb9549fd993` | 8447 | `examples/image_list/lib/main.dart` |
| `3860145280f8ec8cbbcec1a877a51a27c1810ad6` | 8180 | `examples/image_list/lib/main.dart` |
| `14b64e71a639159ceea95ca391ecc172677f8e1c` | 8172 | `examples/image_list/lib/main.dart` |
| `390f0a8c10be425eb1db7b7a0ddaeaf503080150` | 8184 | `examples/image_list/lib/main.dart` |
| `7f5ce670e730c36d96849f5341e0252d2b682669` | 8178 | `examples/image_list/lib/main.dart` |
| `ccbbeb99c2254608b404dabfb27e2f379f717dcf` | 8281 | `examples/image_list/lib/main.dart` |
| `5925cd262069fa9c54c592e3572ff5b65af906ee` | 8285 | `examples/image_list/lib/main.dart` |
| `5c7522263baf37f5d7fba819e8a65c3e06625042` | 8463 | `examples/image_list/lib/main.dart` |
| `408f8f558cab769bbdb853bd9d6aa7ab4c7e29ad` | 8463 | `examples/image_list/lib/main.dart` |
| `6f5c76d9e713c5de2a2085d985e03fd86b4665cf` | 8458 | `examples/image_list/lib/main.dart` |
| `a4a2b6e644cc54bb5ad567804437c72a79d5d507` | 8484 | `examples/image_list/lib/main.dart` |
| `192891b144b78732fe24bdf68694dce71cd83400` | 8518 | `examples/image_list/lib/main.dart` |
| `6dc43e31e59aae5649f86ad22d7ecb4e23813a83` | 8508 | `examples/image_list/lib/main.dart` |
| `c13d68feef3c96ab4b1332b9e16b8ec26b7c21cf` | 8507 | `examples/image_list/lib/main.dart` |
| `a09b3cbbfb9e303d81127d9f34bd913f7467e6f7` | 8481 | `examples/image_list/lib/main.dart` |
| `e63f82c3e5e4f096d6dc103b006e3d91f363b609` | 8451 | `examples/image_list/lib/main.dart` |
| `8be4ee3544333c4751fb04bb62a022fc6218a029` | 8501 | `examples/image_list/lib/main.dart` |
| `79acd1c0abd2cc621cb1b98218cfb3404e77d88d` | 8557 | `examples/image_list/lib/main.dart` |
| `8f54d6a91c74a8660a784ef61d22346e63321561` | 8560 | `examples/image_list/lib/main.dart` |
| `83c524c63a27e8cdd37b72e14c1149dfa7bf2810` | 8534 | `examples/image_list/lib/main.dart` |
| `f5d0431c74af2ac9d2dd0376b78beae093c3367e` | 8357 | `examples/image_list/lib/main.dart` |
| `c2530addad8269d8d63dd2e058b3ec73f6e80b23` | 8351 | `examples/image_list/lib/main.dart` |
| `ac2e3d75c322a5e5cfd8e7e46af4d619d8fad99f` | 8350 | `examples/image_list/lib/main.dart` |
| `cd2208bfae0e399accf9c9750d65f1221676ca11` | 8351 | `examples/image_list/lib/main.dart` |
| `376d157ac3678efb449a0425db7295716f2b4613` | 887 | `packages/flutter_tools/test/data/asset_test/tls_cert/dummy-key.pem` |

## zip (4)

| blob | bytes | path |
| --- | ---: | --- |
| `3dc31910a5388024da4558c9e5f249a37e3783bd` | 37106 | `engine/src/flutter/build/android/CheckInstallApk-debug.apk` |
| `1baf404f77172eb359c84b4ff897744a6a190885` | 33894 | `examples/stocks/android/ic_launcher.zip` |
| `40d114086ef2ca89d1a8502238d2613b53c2b74c` | 4138 | `packages/flutter_tools/test/data/intellij/plugins/Dart/lib/Dart.jar` |
| `3a66e611f519f89421b1089e3416f4fd336d5859` | 1822 | `packages/flutter_tools/test/data/intellij/plugins/flutter-intellij.jar` |

## Kept, but a scanner may note them

- unrecognised binary: 16
