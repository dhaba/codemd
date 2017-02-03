//
// Scripts to build live dashboards on /viz page
//

var ROW_LIM = 7000; // any more than this and we will have to bin by weeks

//var ROW_LIM = 40231; // so rails will run


function buildDashboards(data) {
    console.log('Building dashboards...');
    var commits_json = JSON.parse(data);

    if (Object.keys(commits_json).length < ROW_LIM) {
      console.log("Binning by days...");
      var useWeeks = false;
    } else {
      console.log("Data over row limit. Binning by weeks.");
      var useWeeks = true;
    }

    // Clean commits data, convert dates from unix timestamps to js dates
    var dateFormat = d3.time.format("%x");
    commits_json.forEach(function(d) {
        d.date = new Date(d.date * 1000);
    });

    var commits = crossfilter(commits_json);

    // Date dimensions TODO -- add scalers also, as this will only work for weeks atm
    if (useWeeks) {
        var dateDim = commits.dimension(function(d) { return d3.time.week(d.date); });
        var units = d3.time.weeks;
        var rounder = d3.time.week.round;
    } else { // Use days
        var dateDim = commits.dimension(function(d) { return d3.time.day(d.date); });
        var units = d3.time.days;
        var rounder = d3.time.week.round;
    }

    // Churn metric dimensions
    // var deletionsDim = commits.dimension(function(d) { return d.deletions; });
    var totalDeletionsDim = commits.dimension(function(d) { return d.total_deletions; });
    var totalInsertionsDim = commits.dimension(function(d) { return d.total_insertions; });
    // var totalLocDim = commits.dimension(function(d) { return d.total_insertions - d.total_deletions});

    var authorsDim = commits.dimension(function(d) { return d.author;});

    // Groups and Aggregates
    var dateGroup = dateDim.group()
    var authorDateGroup = dateDim.group()
    var totalChurnByDateGroup = dateDim.group()
    var totalLocByDateGroup = dateDim.group();
    var churnByDateGroup = dateDim.group();
    var bugsByDateGroup = dateDim.group().reduceSum(function(d) {
        return d.bug ? 1 : 0;
    });
    // Plot bugs by day regardless of size, as its static
    bugsDayDim = commits.dimension(function(d) { return d3.time.day(d.date); })
    var bugsByDayGroup = bugsDayDim.group().reduceSum(function(d) {
        return d.bug ? 1 : 0;
    });

    var insertionsByDateGroup = dateDim.group().reduceSum(function(d) {
        return d.insertions;
    });
    var deletionsByDateGroup = dateDim.group().reduceSum(function(d) {
        return d.deletions;
    });
    var netChangeByDateGroup = dateDim.group().reduceSum(function(d) {
        return d.insertions - d.deletions;
    });

    var authorsGroup = authorsDim.group();
    var authorCommitsGroup = authorsGroup.reduceSum();
    var authorLinesGroup = authorsGroup.reduceSum(function(d) {
      return d.insertions + d.deletions;
    })

    var commitsSelected = commits.groupAll().reduceSum()

    // Globals
    var startInsertions = 0;
    var startDeletions = 0;

    // Dates
    var dateRange = {
        minDate: dateDim.bottom(1)[0].date,
        maxDate: dateDim.top(1)[0].date,
    };
    // Color domains
    var bugsDomain = {
        min: 0,
        max: bugsByDateGroup.top(1)[0].value,
    }

    // Compute sums and local optima for insertions and deletions
    var maxReducer = reductio();
    maxReducer.value("insertions").max(function(d) { return d.total_insertions; })
    maxReducer.value("deletions").max(function(d) { return d.total_deletions; })
    maxReducer(totalChurnByDateGroup);

    var aggReducer = reductio();
    aggReducer.value("insertions")
      // .count(true)
      // .max(function(d) { return d.insertions; })
      .sum(function(d) { return d.insertions; });
    aggReducer.value("deletions")
      // .count(true)
      // .max(function(d) { return d.deletions; })
      .sum(function(d) { return d.deletions; });
    aggReducer(churnByDateGroup);


    // console.log('min date: ' + dateRange.minDate);
    // console.log('max date ' + dateRange.maxDate);
    commitsFocusScale = d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]);
    // Commits timeline
    var commitsTimeline = dc.lineChart("#commits-timeline");
    commitsTimeline
        .width(768)
        .height(70)
        .margins({
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
        })
        .dimension(dateDim)
        .group(dateGroup)
        .x(d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]))
        .xUnits(units)
        .round(rounder)
        .renderArea(true)
        .interpolate("basis")
        .renderlet(function(chart) {
            console.log('render let called inside of commitsTimesLine')
            bottom = dateDim.bottom(1)[0];
            if (typeof bottom !== "undefined") {
              startInsertions = bottom.total_insertions;
              startDeletions = bottom.total_deletions;
            } else {
              startInsertions = 0;
              startDeletions = 0;
            }

            churnOverDeletions.redraw()
            //
            //  console.log("(inside adjustVals) min total inserts: " + startInsertions);
            //  console.log("(inside adjustVals) min total deletes: " + startDeletions);
        });

    // var totalCommits = dc.numberDisplay("commits-selected")
    // totalCommits
    //   .formatNumber(d3.format("d"))
    //   .valueAccessor(function(d){return d;})
    //   .group(totalCommits)

    // commitsTimeline.on('filtered', function(chart) {
    //     console.log('commits timeline filtered!!!')
    //     // churnOverDeletions.focus(chart.filters())
    //         // churnOverDeletions.redraw()
    //         // startInsertions = dateDim.bottom(1)[0].total_insertions;
    //         // startDeletions = dateDim.bottom(1)[0].total_deletions;
    //         // churnOverDeletions.focus(chart.filters());
    // })

    // Distribution of defects
    var defectsDistribution = dc.lineChart("#defects-distribution");
    defectsDistribution
        .width(768)
        .height(70)
        .margins({
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
        })
        .colors(d3.scale.quantile().domain([bugsDomain.min, bugsDomain.max])
            .range(["#fb6a4a", "#ef3b2c", "#cb181d", "#a50f15", "#67000d"]))
        .dimension(dateDim)
        .group(bugsByDateGroup)
        .x(commitsFocusScale)
        .xUnits(units)
        .round(rounder)
        .elasticY(true)
        .renderArea(true)
        .brushOn(false)
        .interpolate("basis")
        .rangeChart(commitsTimeline)
        .title(function(d) {
            return "Reported defects: " + d.y;
        })
        // TODO -- add date string to the title above

    // Calculate churn metrics as a function of time interval
    // Churned LOC / Deleted LOC
    function adjustValues(p) {
        var maxInsertions = p.value.insertions.max - startInsertions;
        var maxDeletions = p.value.deletions.max - startDeletions;

        if ((maxInsertions == 0) && (maxDeletions == 0)) {
            maxInsertions += p.value.insertions.max
            maxDeletions += p.value.deletions.max
        }

        if (maxDeletions == 0) {
            maxDeletions = 1;
        } // to prevent 0 division
        var val = (maxInsertions + maxDeletions) / maxDeletions;
        if (isNaN(val) || val < 0) {
            console.log("something has gone terribly wrong lol...");
        }
        // console.log(val)
        return val;
    }

    // M7 - Churned/Deleted (Dev Velocity)
    var churnOverDeletions = dc.lineChart("#churn-over-del");
    churnOverDeletions
        .width(341)
        .height(200)
        .margins({
            top: 10,
            right: 20,
            bottom: 16,
            left: 20
        })
        .x(d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]))
        .xUnits(units)
        .round(rounder)
        .dimension(dateDim)
        .group(totalChurnByDateGroup)
        // .renderArea(true)
        // .colors(['#66339'])
        // .group(churnByDateGroup)
        // .valueAccessor(function(p) {
        //   // Change this to get average?
        //     inserts = p.value.insertions.sum;
        //     deletions = p.value.deletions.sum;
        //     if (deletions == 0) {
        //         deletions += 1;
        //     }
        //     return (inserts + deletions) / deletions
        // })
        .valueAccessor(adjustValues)
        .elasticY(true)
        .renderHorizontalGridLines(true)
        // .yAxisLabel("Churned LOC / Deleted LOC")
        .brushOn(false)
        .yAxisPadding(0.1)
        .yAxis().ticks(5)
    churnOverDeletions.xAxis().ticks(4)

    churnOverDeletions.renderlet(function(chart) {
      chart.selectAll('.dc-chart path.line').style('stroke-width', '2px')
    });

    var totalLoc = dc.lineChart("#total-loc");
    totalLoc
      .width(500)
      .height(350)
      .margins({
          top: 10,
          right: 20,
          bottom: 25,
          left: 50
      })
        .x(commitsFocusScale)
        .xUnits(units)
        .round(rounder)
        .dimension(dateDim)
        .group(totalChurnByDateGroup)
        .valueAccessor(function(p) {
          return p.value.insertions.max - p.value.deletions.max;
        })
        .elasticY(true)
        .renderHorizontalGridLines(true)
        // .yAxisLabel("Churned LOC / Deleted LOC")
        .brushOn(false)
        .interpolate("basis")
        .renderArea(true)
        .colors(['#900C3F'])
        .yAxis().ticks(5)
    totalLoc.xAxis().ticks(4)

    var codeFreq = dc.compositeChart("#code-frequency");
    var insertionsFreq = dc.lineChart(codeFreq);
    var deletionsFreq = dc.lineChart(codeFreq);
    // var netFreq = dc.linechart(codeFreq);

    // netFreq
    //     .group(netChangeByDateGroup)
    //     .colors(['#900C3F'])
    //     .renderArea(true)
    //     .interpolate("basis")
    //     .brushOn(false)

    insertionsFreq
        .group(insertionsByDateGroup)
        .colors(['#2ca02c'])
        .renderArea(true)
        .interpolate("basis")
        .brushOn(false)
        // .on('renderlet', function(chart){
        //   //chart.svg().select('g.chart-body').selectAll('path.line').style('stroke-width', '0px')
        //   // chart.select('g.chart-body').selectAll('path.line').style('stroke-width', '0px');
        // });

    deletionsFreq
        .group(deletionsByDateGroup)
        .colors(["#ef3b2c"])
        .renderArea(true)
        .interpolate("basis")
        .valueAccessor(function(d) {
            return -1 * d.value;
        })
        .brushOn(false)

    codeFreq
        .width(500)
        .height(350)
        .margins({
            top: 10,
            right: 20,
            bottom: 25,
            left: 50
        })
        .x(d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .dimension(dateDim)
        .renderHorizontalGridLines(true)
        .elasticY(true)
        .compose([insertionsFreq, deletionsFreq])//.compose([insertionsFreq, deletionsFreq, netFreq])
        .brushOn(false)
        .mouseZoomable(true)
        .yAxisPadding(0.0)
        .yAxis().ticks(6)

      codeFreq.xAxis().ticks(5)



    commitsTimeline.focusCharts = function(chartlist) {
        if (!arguments.length) {
            return this._focusCharts;
        }
        this._focusCharts = chartlist; // only needed to support the getter above
        this.on('filtered', function(range_chart) {
            if (!range_chart.filter()) {
                dc.events.trigger(function() {
                    chartlist.forEach(function(focus_chart) {
                        focus_chart.x().domain(focus_chart.xOriginalDomain());
                    });
                });
            } else chartlist.forEach(function(focus_chart) {
                if (!rangesEqual(range_chart.filter(), focus_chart.filter())) {
                    dc.events.trigger(function() {
                        focus_chart.focus(range_chart.filter());
                    });
                }
            });
        });
        return this;
    };

    var topAuthors = dc.rowChart('#top-authors');
    topAuthors
      .width(320)
      .height(409)
      .dimension(authorsGroup)
      .group(authorCommitsGroup, "commits")
      .ordering(function(t){return t.commits;})
      .cap(8)
      .elasticX(true)
      .colors(d3.scale.category20b())
      .renderlet(function(chart) {
        chart.svg().selectAll('g.row text').style('fill', 'black');
      })
      .xAxis().ticks(4)

    commitsTimeline.focusCharts([codeFreq, totalLoc, churnOverDeletions,
                                topAuthors, defectsDistribution]);
    dc.renderAll();
}

// $('#top-authors').on('click', function(){
//     // var minDate = tripsByDateDimension.top(5)[4].startDate;
//     // var maxDate = tripsByDateDimension.top(5)[0].startDate;
//     // console.log(tripVolume.filters());
//     //
//     //
//     // tripVolume.filter([minDate, maxDate]);
//     // tripVolume.x(d3.time.scale().domain([minDate,maxDate]));
//     //
//     // console.log(tripVolume.filters());
//
//     dc.redrawAll()
// });


// To overwrite chart and add multiple filters
function rangesEqual(range1, range2) {
    if (!range1 && !range2) {
        return true;
    } else if (!range1 || !range2) {
        return false;
    } else if (range1.length === 0 && range2.length === 0) {
        return true;
    } else if (range1[0].valueOf() === range2[0].valueOf() &&
        range1[1].valueOf() === range2[1].valueOf()) {
        return true;
    }
    return false;
  }



  // churnOverDeletions.on('preRedraw', function(chart) {
  //     // console.log('preRedraw called');
  //     // startInsertions = dateDim.bottom(1)[0].total_insertions;
  //     // startDeletions = dateDim.bottom(1)[0].total_deletions;
  //     //  console.log("(inside adjustVals) min total inserts: " + startInsertions);
  //     //  console.log("(inside adjustVals) min total deletes: " + startDeletions);
  // });

  // churnOverDeletions.on('preRender', function(chart) {
  //     console.log('preRender called');
  // });
  // churnOverDeletions.on('renderlet', function(chart) {
  //     console.log('renderlet called');
  // });
  // churnOverDeletions.on('postRedraw', function(chart) {
  //     console.log('postRedraw called');
  // });
  // churnOverDeletions.on('filtered', function(chart, zoom) {
  //     console.log('(CHURN OVER DEL) filtered called');
  // });
  // churnOverDeletions.on('zoomed', function(chart, filter) {
  //     console.log('zoomed called');
  // });
  // churnOverDeletions.on('zoomed', function(chart, filter) {
  //     console.log('zoomed called');
  // });
