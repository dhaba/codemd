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

    var dateDim = commits.dimension(function(d) { return d.date; });
    // TODO -- simplify below using 'pluck'
    var deletionsDim = commits.dimension(function(d) { return d.deletions; });
    var insertionsDim = commits.dimension(function(d) { return d.insertions; });
    var netLinesDim = commits.dimension(function(d) { return d.insertions - d.deletions; })

    // Reduce function for running total
    // var reduceRunningTotal = reductio()
    //   .custom({
    //     add: function(p, v) {
    //       p.insertions += v.insertions;
    //       p.deletions += v.deletions;
    //       return p;
    //     },
    //     remove: function(p, v) {
    //       p.insertions += v.insertions;
    //       p.deletions += v.deletions;
    //     },
    //     initial: function(p) {
    //       p.insertions = 0;
    //       p.deletions = 0;
    //       return p;
    //     }
    // });
  //
    // function accumulateGroup(source_group) {
    //   return {
    //       all:function () {
    //           var cum_insertions = 0;
    //           var cum_deletions = 0;
    //           return source_group.all().map(function(d) {
    //               cum_insertions += d.insertions;
    //               cum_deletions += d.deletions;
    //               // d.insertions = cum_insertions;
    //               // d.deletions = cum_deletions;
    //               // return d;
    //               return {date: d.date, insertions: cum_insertions, deletions: cum_deletions};
    //           });
    //       }
    //     };
    // }

  function reduceAdd(p, v) {
       p.total += v.insertions;
       return p;
  }

  function reduceRemove(p, v) {
      p.total -= v.insertions;
      return p;
  }

  function reduceInitial() {
    return {total: 0};
  }

    // Grouped/aggregated metrics
    var numCommitsByWeek = dateDim.group(function(d) { return d3.time.week(d);  });
    var aggregatedLines = insertionsDim.group().reduce(reduceAdd, reduceRemove, reduceInitial);

    // console.log(aggregatedLines.all());

    // reduceRunningTotal(aggregatedLines);

    // var deletionsToDate = reduceRunningTotal(dateDim.group());
    // var insertionsToDate = reduceRunningTotal(dateDim.group());


    //Define values (to be used in charts) TODO -- i can just elastic scale??
    // var minDate = dateDim.bottom(1)[0].date;
    // var maxDate = dateDim.top(1)[0].date;
    // console.log('min date: ' + minDate);
    // console.log('max date ' + maxDate);

    // Commits timeline
    var commitsTimeline = dc.barChart("#commits-timeline");
    commitsTimeline
        .width(750)
        .height(200)
        .margins({
            top: 10,
            right: 25,
            bottom: 35,
            left: 25
        })
        .dimension(dateDim)
        .group(numCommitsByWeek)
        .transitionDuration(500)
        .x(d3.time.scale()) //.x(d3.time.scale().domain([minDate, maxDate]))
        .elasticX(true)
        .xUnits(d3.time.weeks)
        .elasticY(false)
        .xAxisLabel("Commits By Week")
        .yAxis().ticks(4);

    // Code Churn

    var codeChurn = dc.compositeChart("#code-churn");
    codeChurn
      .width(400)
      .height(350)
      // .margins({top: 20, left: 10, right: 10, bottom: 20})
      .dimension(dateDim)
      .x(d3.time.scale())
      .elasticX(true)
      .elasticY(true)
      // .xUnits(d3.time.weeks)
      .yAxisLabel("Lines of Code")
      .legend(dc.legend().x(80).y(50).itemHeight(13).gap(5))
      .renderHorizontalGridLines(true)
      .compose([
        // dc.lineChart(codeChurn)
        //   .dimension(deletionsDim)
        //   // .group(aggregatedLines, "Deletions")
        //   .colors(['#f44242']),
        dc.lineChart(codeChurn)
          // .dimension(insertionsDim)
          .group(aggregatedLines, "Insertions")
          .valueAccessor(function (d) {
            return d.value.total;
          })
          .colors(['#42f456'])
      ])
      .brushOn(false);

    // Test chart to debug data
    var dataTable = dc.dataTable("#data-table");
    dataTable
      .width(800)
      .height(600)
      .dimension(dateDim)
      // .group(aggregatedLines)
      .group(function(d) { return "Some Key"; } )
      .size(10)
      .columns([
        function(d) { return d.insertions; },
        function(d) { return d.deletions; },
        function(d) { return d.author; },
        function(d) { return d.date; }
      ])
      .sortBy(function(d) { return d.date; })
      .order(d3.descending);

    dc.renderAll();
}
