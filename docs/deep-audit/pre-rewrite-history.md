# Local pre-rewrite Git bundle

Claude's external rice memory pointed to ~/blackwall-pre-rewrite-20260919-0039.bundle. The109,835,242byte bundle exists and lists dev/nuc/remote refs. It was inspected in a private temporary bare object database under the user runtime directory; both temporary databases were automatically removed. No credential blob or object pack was retained in audit artifacts.

The old bundle has139reachablecommits. Its132nonempty patches after excluding scripts/c2a match current reachable patch bytes exactly by SHA256, not merely whitespace-insensitive patch-id. The remaining commits are empty/merge content in that comparison. Thus the existing current-history semantic review can also cover those duplicate noncredential changes; the map preserves exact old/current commit IDs. This is content deduplication, not a separate historical test rerun.

Two old commits directly name scripts/c2a: original682bde89acf911faba43629fae46de46c37f2b4f and removal1ee7d5742c5146f54377bb3ad43a84be0c59f382. Structural inspection of the original blob confirms literal sshpass password arguments, without printing or copying their values. This is stronger evidence than the current rewritten log, where the path is absent. The bundle proves the old credential-bearing path existed; it does not independently establish the historical public-exposure duration, repository deletion/recreation, rotation status, or present compromise claimed in memory. None of those were acted on.

Evidence metadata: pre-rewrite-history.json, pre-rewrite-exact-diff-map.json, pre-rewrite-c2a-structure.json. Exact duplicates inherit their current patch review state; do not mark all139semanticallyclosed until the representative current patches are read.
