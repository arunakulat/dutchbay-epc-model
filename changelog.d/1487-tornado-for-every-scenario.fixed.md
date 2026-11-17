- The one-way sensitivity tornado now runs on a scenario that declares its generation per
  technology (#1787, #1487 item 3). The capacity-factor driver scales each technology's
  capacity factor with the project figure, so the pipeline's year-1 reconciliation holds at
  every shocked point. The DutchBay solar-only and hybrid scenarios and the Blue Whale wind
  and hybrid scenarios now get a tornado. Every other scenario's tornado is unchanged.
  - The solar assessment report runs its one-way sensitivity on a per-technology scenario
    instead of listing it as not run.
  - The report tornado's heading and caption name the swept metric, its columns read
    "Downside case" and "Upside case", and a driver whose swing is undefined is listed
    after every defined one, as the caption now says (#1487 item 1).
  - The web results tornado shows an undefined value as "undefined", with a note, rather
    than a dash.
  - The comment on the debt-tenor driver no longer says it is flat for the project IRR: on
    the DutchBay lender case it is not (#1487 item 2, a finance question left open).
