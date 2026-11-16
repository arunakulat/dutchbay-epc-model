- Each DutchBay turbine now has its own live PyWake wake loss and waked wind rose, recorded
  as a labelled resource sensitivity (#1589, owner's card 2026-11-16 "Build it, reopen
  #1589"). `wind_resource.bankable_aep.model_wake_loss` returns every turbine's gross and
  waked energy, its loss and its loss and energy share by wind-rose sector, beside the farm
  figures it computes exactly as before. The wake re-baseline runner adds a
  `per_turbine_sensitivity` block to `docs/wind/dutchbay_14_turbine_wake_summary.json`: each
  turbine's live loss, the same loss scaled so the farm total sits on the lender basis
  (`wake_loss_14_pct`, 7.32%), and its roses. Setting
  `wake_rebaseline.per_turbine_rose_png` draws the roses through the new
  `app.reports.wind_rose_plot.render_turbine_wake_roses_png`. The lender basis, every
  scenario and every KPI are unchanged; the gap between the live farm loss and the frozen
  value stays open in #1589.
