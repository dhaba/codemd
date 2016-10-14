//
// Scripts to build live dashboards on /viz page
//

function buildDashboards(data) {
    // console.log(data)
    // $("#json-data").html(data);

    // Clean commits data; convert dates from unix timestamps to js dates
    var commits_json = JSON.parse(data);
    var dateFormat = d3.time.format("%x");
    commits_json.forEach(function(d) {
        d.date = new Date(d.date * 1000);
    });
    var commits = crossfilter(commits_json);

    // Date dimensions
    var dateDim = commits.dimension(function(d) { return d.date; });
    var dayDim =  commits.dimension(function(d) { return d3.time.day(d.date); });
    var weekDim = commits.dimension(function(d) { return d3.time.week(d.date); });

    // Churn metric dimensions
    var deletionsDim = commits.dimension(function(d) { return d.deletions; });
    var totalDeletionsDim = commits.dimension(function(d) { return d.total_deletions; });

    var insertionsDim = commits.dimension(function(d) { return d.insertions; });
    var totalInsertionsDim = commits.dimension(function(d) { return d.total_insertions; });

    var netLinesDim = commits.dimension(function(d) { return d.insertions - d.deletions; });
    var totalLocDim = commits.dimension(function(d) { return d.total_insertions - d.total_deletions; });

    // Groups and Aggregates
    var weekGroup = weekDim.group()
    var bugsByWeekGroup = weekDim.group().reduceSum( function (d) {
      return d.bug ? 1 : 0;
    })

    var reducer = reductio()
    reducer.value("insertions").max(function(d) { return d.total_insertions; })
    reducer.value("deletions").max(function(d) { return d.total_deletions; })

    var totalInsertionsByWeekGroup = weekDim.group();
    reducer(totalInsertionsByWeekGroup)

    //Define values (to be used in charts) TODO -- i can just elastic scale??
    var dateRange = {
      minDay: dayDim.bottom(1)[0].date,
      maxDay: dayDim.top(1)[0].date,
      minWeek: weekDim.bottom(1)[0].date,
      maxWeek: weekDim.top(1)[0].date,
      minDate: dateDim.bottom(1)[0].date,
      maxDate: dateDim.top(1)[0].date
    };

    console.log('min date: ' + dateRange.minDate);
    console.log('max date ' + dateRange.maxDate);
    console.log('\nmin week date: ' + dateRange.minWeek);
    console.log('max week date ' + dateRange.maxWeek);

    // Commits timeline
    var commitsTimeline = dc.barChart("#commits-timeline");
    commitsTimeline
        .width(990)
        .height(50)
        .margins({
            top: 15,
            right: 0,
            bottom: 20,
            left: 0
        })
        .dimension(weekDim)
        .group(weekGroup)
        .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .gap(1)
        .centerBar(true)

    // Defects Distribution
    var defectsDistribution = dc.barChart("#defects-distribution");
    defectsDistribution
        .width(990)
        .height(75)
        .margins({
            top: 0,
            right: 0,
            bottom: 20,
            left: 0
        })
        .dimension(weekDim)
        .group(bugsByWeekGroup)
        .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .centerBar(true)

    // M7 - Churned/Deleted (Development Velocity)
    var churnOverDeletions = dc.lineChart("#churn-over-del");
    churnOverDeletions
        .width(990)
        .height(150)
        .margins({
            top: 30,
            right: 0,
            bottom: 40,
            left: 0
        })
        .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .dimension(weekDim)
        .group(totalInsertionsByWeekGroup)
        .valueAccessor(function(p) {
            return (p.value.insertions.max + p.value.deletions.max) / p.value.deletions.max;
        })
        .rangeChart(commitsTimeline)
        .elasticY(true)
        .renderHorizontalGridLines(true)
        .xAxisLabel("Churned LOC / Deleted LOC")
        .brushOn(false)
        .yAxisPadding(0.1)

      // M1 - Churned/Total (Indicative of Defects)
      var churnOverTotal = dc.lineChart("#churn-over-total");
      churnOverTotal
          .width(990)
          .height(150)
          .margins({
              top: 30,
              right: 0,
              bottom: 40,
              left: 0
          })
          .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
          .xUnits(d3.time.weeks)
          .round(d3.time.week.round)
          .dimension(weekDim)
          .group(totalInsertionsByWeekGroup)
          .valueAccessor(function(p) {
              return (p.value.insertions.max + p.value.deletions.max) / p.value.deletions.max;
          })
          .rangeChart(commitsTimeline)
          .elasticY(true)
          .renderHorizontalGridLines(true)
          .xAxisLabel("Churned LOC / Deleted LOC")
          .brushOn(false)
          .yAxisPadding(0.1)




    // var codeChurn = dc.compositeChart("#code-churn");
    // codeChurn
    //   .width(400)
    //   .height(350)
    //   // .margins({top: 20, left: 10, right: 10, bottom: 20})
    //   .dimension(dateDim)
    //   .x(d3.time.scale())
    //   .elasticX(true)
    //   .elasticY(true)
    //   // .xUnits(d3.time.weeks)
    //   .yAxisLabel("Lines of Code")
    //   .legend(dc.legend().x(80).y(50).itemHeight(13).gap(5))
    //   .renderHorizontalGridLines(true)
    //   .compose([
    //     // dc.lineChart(codeChurn)
    //     //   .dimension(deletionsDim)
    //     //   // .group(aggregatedLines, "Deletions")
    //     //   .colors(['#f44242']),
    //     dc.lineChart(codeChurn)
    //       // .dimension(insertionsDim)
    //       .group(aggregatedLines, "Insertions")
    //       .valueAccessor(function (d) {
    //         return d.value.total;
    //       })
    //       .colors(['#42f456'])
    //   ])
    //   .brushOn(false);

    // Test chart to debug data
    // var dataTable = dc.dataTable("#data-table");
    // dataTable
    //   .width(800)
    //   .height(600)
    //   .dimension(dateDim)
    //   // .group(aggregatedLines)
    //   .group(function(d) { return "Some Key"; } )
    //   .size(10)
    //   .columns([
    //     function(d) { return d.insertions; },
    //     function(d) { return d.deletions; },
    //     function(d) { return d.author; },
    //     function(d) { return d.date; }
    //   ])
    //   .sortBy(function(d) { return d.date; })
    //   .order(d3.descending);

    // var weeklyRollingChurnGroup = commits.groupAll().reduce(
    //     /* callback for when data is added to the current filter results */
    //     function(p, v) {
    //         ++p.count;
    //         p.rollingInsertions += v.insertions;
    //         return p;
    //     },
    //     /* callback for when data is removed from the current filter results */
    //     function(p, v) {
    //         --p.count;
    //         p.rollingInsertions -= v.insertions;
    //         return p;
    //     },
    //     /* initialize p */
    //     function() {
    //         return {
    //             count: 0,
    //             rollingInsertions: 0
    //         };
    //     }
    // );

    // Grouped/aggregated metrics
    // var numCommitsByWeek = dateDim.group(function(d) { return d3.time.week(d);  });
    // var aggregatedLines = insertionsDim.group().reduce(reduceAdd, reduceRemove, reduceInitial);

    // console.log(aggregatedLines.all());

    // reduceRunningTotal(aggregatedLines);

    // var deletionsToDate = reduceRunningTotal(dateDim.group());
    // var insertionsToDate = reduceRunningTotal(dateDim.group());


    dc.renderAll();
}
