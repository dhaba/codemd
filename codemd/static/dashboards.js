var ROW_LIM = 7000; // any more than this and we will have to bin by weeks
//var ROW_LIM = 40231; // rails will run in full glory (but lags on shitty computers)
var LEFT_COL_WIDTH = 290;

function buildDashboards(data, projectName) {
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
    var totalDeletionsDim = commits.dimension(function(d) { return d.total_deletions; });
    var totalInsertionsDim = commits.dimension(function(d) { return d.total_insertions; });

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
    var  authorCommitsGroup = authorsGroup.reduceSum();
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
      .sum(function(d) { return d.insertions; });
    aggReducer.value("deletions")
      .sum(function(d) { return d.deletions; });
    aggReducer(churnByDateGroup);

    // console.log('min date: ' + dateRange.minDate);
    // console.log('max date ' + dateRange.maxDate);

    commitsFocusScale = d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]);

    // Commits timeline
    var commitsTimeline = dc.lineChart("#commits-timeline");
    var commitsTimelineSize = getParentSize('#commits-timeline');
    commitsTimeline
        .width(commitsTimelineSize.width)
        .height(commitsTimelineSize.height)
        .margins({
            top: 4,
            right: 0,
            bottom: 16,
            left: 28
        })
        .dimension(dateDim)
        .group(dateGroup)
        .x(d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]))
        .xUnits(units)
        .round(rounder)
        .renderArea(true)
        .interpolate("basis")
        .renderlet(function(chart) {
            bottom = dateDim.bottom(1)[0];
            if (typeof bottom !== "undefined") {
              startInsertions = bottom.total_insertions;
              startDeletions = bottom.total_deletions;
            } else {
              startInsertions = 0;
              startDeletions = 0;
            }
            churnOverDeletions.redraw();
        });

    commitsTimeline.yAxis().ticks(2);

    var all = commits.groupAll();
    var allBugs = commits.groupAll().reduceSum(function(d) {
      return d.bug ? 1 : 0;
    });

    var totalCommits = dc.numberDisplay("#total-commits")
    .formatNumber(d3.format("d"))
    .valueAccessor(function(d){
      return d;
    })
    .group(all);

    var totalBugs = dc.numberDisplay("#total-bugs")
    .formatNumber(d3.format("d"))
    .valueAccessor(function(d){
      return d;
    })
    .group(allBugs);

    // Distribution of defects
    var defectsDistribution = dc.lineChart("#defects-distribution");
    var defectsDistributionSize = getParentSize("#defects-distribution");
    defectsDistribution
        .width(defectsDistributionSize.width)
        .height(defectsDistributionSize.height)
        .margins({
          top: 4,
          right: 0,
          bottom: 16,
          left: 28
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
        .rangeChart(commitsTimeline);
        // TODO -- add date string to the title above

    defectsDistribution.yAxis().ticks(2);

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
            // console.log("something has gone terribly wrong lol...");
        }
        // console.log(val)
        return val;
    }

    // M7 - Churned/Deleted (Dev Velocity)
    var churnOverDeletions = dc.lineChart("#churn-over-del");
    var churnOverDeletionsSize = getParentSize("#churn-over-del");
    churnOverDeletions
        .width(churnOverDeletionsSize.width)
        .height(churnOverDeletionsSize.height)
        .margins({
            top: 4,
            right: 8,
            bottom: 20,
            left: 16
        })
        .x(commitsFocusScale)
        .xUnits(units)
        .round(rounder)
        .dimension(dateDim)
        .group(totalChurnByDateGroup)
        .valueAccessor(adjustValues)
        .elasticY(true)
        .renderHorizontalGridLines(true)
        .brushOn(false)
        .yAxisPadding(0.1)
        .yAxis().ticks(5)
    churnOverDeletions.xAxis().ticks(4)

    churnOverDeletions.renderlet(function(chart) {
      chart.selectAll('.dc-chart path.line').style('stroke-width', '2px')
    });

    var totalLoc = dc.lineChart("#total-loc");
    var totalLocSize = getParentSize("#total-loc");
    totalLoc
      .width(totalLocSize.width)
      .height(totalLocSize.height)
      .margins({
          top: 10,
          right: 5,
          bottom: 20,
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
      .brushOn(false)
      .interpolate("basis")
      .renderArea(true)
      .colors(['#900C3F'])
      .yAxis().ticks(5);

    totalLoc.xAxis().ticks(4);

    var codeFreq = dc.compositeChart("#code-frequency");
    var codeFreqSize = getParentSize("#code-frequency");
    var insertionsFreq = dc.lineChart(codeFreq);
    var deletionsFreq = dc.lineChart(codeFreq);


    insertionsFreq
        .group(insertionsByDateGroup)
        .colors(['#2ca02c'])
        .renderArea(true)
        .interpolate("basis")
        .brushOn(false);

    deletionsFreq
        .group(deletionsByDateGroup)
        .colors(["#ef3b2c"])
        .renderArea(true)
        .interpolate("basis")
        .valueAccessor(function(d) {
            return -1 * d.value;
        })
        .brushOn(false);

    codeFreq
        .width(codeFreqSize.width)
        .height(codeFreqSize.height)
        .margins({
            top: 10,
            right: 5,
            bottom: 20,
            left: 50
        })
        .x(commitsFocusScale)
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .dimension(dateDim)
        .renderHorizontalGridLines(true)
        .elasticY(true)
        .compose([insertionsFreq, deletionsFreq])
        .brushOn(false)
        .mouseZoomable(false)
        .yAxisPadding(0.0)
        .yAxis().ticks(6);

      codeFreq.xAxis().ticks(5);

    commitsTimeline.focusCharts = function(chartlist) {
        // if (!arguments.length) {
        //     return this._focusCharts;
        // }
        // this._focusCharts = chartlist; // only needed to support the getter above
        // this.on('filtered', function(range_chart) {
        //     if (!range_chart.filter()) {
        //         dc.events.trigger(function() {
        //             chartlist.forEach(function(focus_chart) {
        //                 focus_chart.x().domain(focus_chart.xOriginalDomain());
        //             });
        //         });
        //     } else chartlist.forEach(function(focus_chart) {
        //         if (!rangesEqual(range_chart.filter(), focus_chart.filter())) {
        //             dc.events.trigger(function() {
        //                 focus_chart.focus(range_chart.filter());
        //             });
        //         }
        //     });
        // });
        // return this;
    };

    var topAuthors = dc.rowChart('#top-authors');
    var topAuthorsSize = getParentSize('#top-authors');
    topAuthors
      .width(topAuthorsSize.width)
      .height(topAuthorsSize.height)
      .margins({
          top: 0,
          right: 10,
          bottom: 20,
          left: 10
      })
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

    // Bind bind buttons
    $('#cp-btn').on('click', function (e) {
      start1 = dateDim.bottom(1)[0].date.getTime() / 1000;
      end1 = dateDim.top(1)[0].date.getTime() / 1000;
      urlParams = projectName + "?start1=" + start1 + "&end1=" + end1;
      hotspotsURL = "http://" + window.location.host + "/circle_packing/" + urlParams;
      console.log(hotspotsURL);
      window.location.href = hotspotsURL;
   });
   $('#reset-btn').on('click', function (e) {
     dc.filterAll();
     dc.redrawAll();
   });
   $('#tutorial-btn').on('click', function (e) {
     introJs().start();
   });
}

function setAutoResize(callback) {
  var rtime;
  var timeout = false;
  var delta = 200;
  $(window).resize(function() {
    rtime = new Date();
    if (timeout === false) {
      timeout = true;
      setTimeout(resizeend, delta);
    }
  });

  function resizeend() {
    if (new Date() - rtime < delta) {
      setTimeout(resizeend, delta);
    } else {
      timeout = false;
      callback();
    }
  }
}

function getParentSize(elementId) {
  var width = $(elementId).parent().width();
  var height = $(elementId).parent().height();
  return {'width': width, 'height': height};
}

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
