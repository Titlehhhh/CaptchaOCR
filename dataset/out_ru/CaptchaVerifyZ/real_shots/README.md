# CaptchaVerifyZ - 5 reference renders

These are **not** generated samples. They are re-renders of the upstream renderer
algorithm, produced by `research/RefRender.java` (a hand transcription of the CFR decompile
of `CaptchaVerifyZ-1.4.jar`, itself checked against the raw bytecode):

```
ref-00000.png   ref-A7K2X.png   ref-M3P9L.png   ref-QWERT.png   ref-ZZZZZ.png
```

They are the ground truth for the pixel-identity check in `research/DiffCaptchaVerifyZ.java`:
the project's own generator renders the same five codes and the result is **0 differing
pixels out of 16384** with an equal MD5, for all five.

The originals are in `research/refout/`.
