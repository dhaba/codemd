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
    // Define dimensions
    var dateDim = commits.dimension(function(d) { return d.date; });
    var weekDim = commits.dimension(function(d) { return d3.time.week(d.date); });

    var deletionsDim = commits.dimension(function(d) { return d.deletions; });
    var insertionsDim = commits.dimension(function(d) { return d.insertions; });
    var netLinesDim = commits.dimension(function(d) { return d.insertions - d.deletions; })

    // Groups and Aggregates
    var weekGroup = weekDim.group()
    var insertionsByWeekGroup = weekDim.group().reduceSum(function (d) {
      return d.insertions;
    })
    var insertionsByDateGroup = dateDim.group().reduceSum(function (d) {
      return d.insertions;
    })

    // Grouped/aggregated metrics
    // var numCommitsByWeek = dateDim.group(function(d) { return d3.time.week(d);  });
    // var aggregatedLines = insertionsDim.group().reduce(reduceAdd, reduceRemove, reduceInitial);

    // console.log(aggregatedLines.all());

    // reduceRunningTotal(aggregatedLines);

    // var deletionsToDate = reduceRunningTotal(dateDim.group());
    // var insertionsToDate = reduceRunningTotal(dateDim.group());


    //Define values (to be used in charts) TODO -- i can just elastic scale??
    var dateRange = {
      minWeek: weekDim.bottom(1)[0].date,
      maxWeek: weekDim.top(1)[0].date
    };
    var minWeek = weekDim.bottom(1)[0].date;
    var maxWeek = weekDim.top(1)[0].date;
    console.log('min week date: ' + minWeek);
    console.log('max week date ' + maxWeek);

    // Commits timeline
    var commitsTimeline = dc.barChart("#commits-timeline");
    commitsTimeline
        .width(990)
        .height(50)
        .margins({
            top: 0,
            right: 50,
            bottom: 20,
            left: 50
        })
        .dimension(weekDim)
        .group(weekGroup)
        .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .gap(1)
        .centerBar(true)

    // Rolling insertions
    var rollingInsertions = dc.lineChart("#rolling-insertions");
    rollingInsertions
      .width(990)
      .height(150)
      .margins({
          top: 0,
          right: 50,
          bottom: 20,
          left: 50
      })
      .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
      .xUnits(d3.time.weeks)
      .round(d3.time.week.round)
      .dimension(weekDim)
      .group(insertionsByWeekGroup)
      .rangeChart(commitsTimeline)
      .elasticY(true)
      .renderHorizontalGridLines(true)
      .brushOn(false)

    // Code Churn

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

    dc.renderAll();
}
