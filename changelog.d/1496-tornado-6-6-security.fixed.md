Advance the existing Tornado lock pin from 6.5.9 to 6.6 for #1496. Upstream
identifies 6.6 as the fix for GHSA-pcg2-g6cj-q92c (folded-header parsing CPU
complexity), GHSA-pw9p-v7r6-gx4p (RedirectHandler open redirect), and
GHSA-r4j5-9xpp-3985 (chunked-body event-loop blocking and excessive memory).
No abstract dependency, policy constraint, advisory suppression, application
source, or financial assumption changes.
