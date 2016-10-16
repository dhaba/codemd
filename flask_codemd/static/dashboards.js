//
// Scripts to build live dashboards on /viz page
//

function buildDashboards(data) {
    console.log('Building dashboards...');

    var useWeeks = true; // global toggle, otherwise use days

    // Clean commits data, convert dates from unix timestamps to js dates
    var commits_json = JSON.parse(data);
    var dateFormat = d3.time.format("%x");
    commits_json.forEach(function(d) {
        d.date = new Date(d.date * 1000);
    });

    var commits = crossfilter(commits_json);

    // Date dimensions TODO -- add scalers also, as this will only work for weeks atm
    if (useWeeks) {
        var dateDim = commits.dimension(function(d) {
            return d3.time.week(d.date);
        });
    } else { // Use days
        var dateDim = commits.dimension(function(d) {
            return d3.time.day(d.date);
        });
    }

    // Churn metric dimensions
    var deletionsDim = commits.dimension(function(d) {
        return d.deletions;
    });
    var totalDeletionsDim = commits.dimension(function(d) {
        return d.total_deletions;
    });

    var insertionsDim = commits.dimension(function(d) {
        return d.insertions;
    });
    var totalInsertionsDim = commits.dimension(function(d) {
        return d.total_insertions;
    });

    // Groups and Aggregates
    var dateGroup = dateDim.group()
    var totalChurnByDateGroup = dateDim.group();
    var churnByDateGroup = dateDim.group();
    var bugsByDateGroup = dateDim.group().reduceSum(function(d) {
        return d.bug ? 1 : 0;
    })

    // Globals
    var startInsertions = 30840;
    var startDeletions = 0;
    var needsResetStart = true;

    // Compute sums and local optima for insertions and deletions
    var maxReducer = reductio();
    maxReducer.value("insertions").max(function(d) { return d.total_insertions; })
    maxReducer.value("deletions").max(function(d) { return d.total_deletions; })
    maxReducer(totalChurnByDateGroup)

    var aggReducer = reductio();
    aggReducer.value("insertions").max(function(d) { return d.insertions; })
    aggReducer.value("deletions").max(function(d) { return d.deletions; })
    aggReducer(churnByDateGroup);

    // Define range values
    var dateRange = {
        minDate: dateDim.bottom(1)[0].date,
        maxDate: dateDim.top(1)[0].date,
    };
    // console.log('min date: ' + dateRange.minDate);
    // console.log('max date ' + dateRange.maxDate);

    // Commits timeline
    var commitsTimeline = dc.lineChart("#commits-timeline");
    commitsTimeline
        .width(900)
        .height(70)
        .margins({
            top: 10,
            right: 10,
            bottom: 20,
            left: 10
        })
        .dimension(dateDim)
        .group(dateGroup)
        .x(d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .renderArea(true)
        .interpolate("basis")
        .renderlet(function(chart) {
            // console.log('render let called!!!!')
            chart.svg().selectAll('.chart-body').attr('clip-path', null);
            startInsertions = dateDim.bottom(1)[0].total_insertions;
            startDeletions = dateDim.bottom(1)[0].total_deletions;
            // churnOverDeletions.focus(chart.filters());
        })

    commitsTimeline.on('filtered', function(chart) {
        console.log('commits timeline filtered!!!. Filtering churn chart')
            // startInsertions = dateDim.bottom(1)[0].total_insertions;
            // startDeletions = dateDim.bottom(1)[0].total_deletions;
            // churnOverDeletions.focus(chart.filters());
    })

    // Distribution of defects
    var defectsDistribution = dc.barChart("#defects-distribution");
    defectsDistribution
        .width(900)
        .height(60)
        .margins({
            top: 10,
            right: 40,
            bottom: 20,
            left: 40
        })
        .dimension(dateDim)
        .group(bugsByDateGroup)
        .x(d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .centerBar(true)
        .brushOn(false)
        .title(function(d) {
            return "Reported defects: " + d.y;
        })
        // TODO -- add date string to the title above

    // Calculate churn metrics as a function of time interval
    // Churned LOC / Deleted LOC
    function adjustValues(p) {
      // TODO -- optimize this method
        dc.events.trigger(function() {
          // startInsertions = dateDim.bottom(1)[0].total_insertions;
          // startDeletions = dateDim.bottom(1)[0].total_deletions;
          //
          // newStart = dateDim.bottom(1)[0].total_insertions;
          // newDeletion = dateDim.bottom(1)[0].total_deletions;
          //
          // if ((newStart != startInsertions) && (startDeletions != newDeletion)) {
          //   console.log('vals changing...');
          //   startInsertions = newStart;
          //   startDeletions = newDeletion;
          //   console.log("(inside adjustVals) min total inserts: " + startInsertions);
          //   console.log("(inside adjustVals) min total deletes: " + startDeletions);
          // }

          // console.log("(inside adjustVals) min total inserts: " + startInsertions);
          // console.log("(inside adjustVals) min total deletes: " + startDeletions);
        });
        var maxInsertions = p.value.insertions.max - startInsertions;
        var maxDeletions = p.value.deletions.max - startDeletions;

        if ((maxInsertions == 0) && (maxDeletions == 0)) {
          maxInsertions += p.value.insertions.max
          maxDeletions += p.value.deletions.max
        }

        if (maxDeletions == 0) { maxDeletions = 1; } // to prevent 0 division
        var val = (maxInsertions + maxDeletions) / maxDeletions;
        if (isNaN(val)) {
            console.log("something has gone terribly wrong lol...");
        }
        return val;

        var inserts = p.value.insertions.max;
        var deletions = p.value.deletions.max;
    }

    // M7 - Churned/Deleted (Dev Velocity)
    var churnOverDeletions = dc.lineChart("#churn-over-del");
    churnOverDeletions
        .width(990)
        .height(150)
        .margins({
            top: 30,
            right: 40,
            bottom: 40,
            left: 40
        })
        .x(d3.time.scale().domain([dateRange.minDate, dateRange.maxDate]))
        .xUnits(d3.time.weeks)
        .round(d3.time.week.round)
        .dimension(dateDim)
        .group(totalChurnByDateGroup)
        // .valueAccessor(function(p) {
        //   inserts = p.value.insertions.max;
        //   deletions = p.value.deletions.max;
        //   if (deletions == 0) { deletions += 1; }
        //   return (inserts + deletions) / deletions
        // })
        .valueAccessor(adjustValues)
        .rangeChart(commitsTimeline)
        .elasticY(true)
        .renderHorizontalGridLines(true)
        // .yAxisLabel("Churned LOC / Deleted LOC")
        .brushOn(false)
        .yAxisPadding(0.1)
        .yAxis().ticks(6)

    churnOverDeletions.on('preRender', function(chart) {
        console.log('preRender called');
    });
    churnOverDeletions.on('renderlet', function(chart) {
        console.log('renderlet called');
    });
    churnOverDeletions.on('postRedraw', function(chart) {
        console.log('postRedraw called');
        // needsResetStart = true;
    });
    churnOverDeletions.on('preRedraw', function(chart) {
      //   console.log('preRedraw called');
      //   startInsertions = dateDim.bottom(1)[0].total_insertions;
      //  startDeletions = dateDim.bottom(1)[0].total_deletions;
      //    console.log("(inside adjustVals) min total inserts: " + startInsertions);
      //    console.log("(inside adjustVals) min total deletes: " + startDeletions);
    });
    churnOverDeletions.on('filtered', function(chart, zoom) {
        console.log('(CHURN OVER DEL) filtered called');
    });
    churnOverDeletions.on('zoomed', function(chart, filter) {
        console.log('zoomed called');
    });


    churnOverDeletions.on('zoomed', function(chart, filter) {
        console.log('zoomed called');
    });
    // M1 - Churned/Total (Indicative of Defects)
    // var churnOverTotal = dc.lineChart("#churn-over-total");
    // churnOverTotal
    //     .width(990)
    //     .height(150)
    //     .margins({
    //         top: 30,
    //         right: 0,
    //         bottom: 40,
    //         left: 0
    //     })
    //     .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
    //     .xUnits(d3.time.weeks)
    //     .round(d3.time.week.round)
    //     .dimension(weekDim)
    //     .group(totalInsertionsByWeekGroup)
    //     .valueAccessor(function(p) {
    //         return (p.value.insertions.max + p.value.deletions.max) / p.value.deletions.max;
    //     })
    //     .rangeChart(commitsTimeline)
    //     .elasticY(true)
    //     .renderHorizontalGridLines(true)
    //     .xAxisLabel("Churned LOC / Deleted LOC")
    //     .brushOn(false)
    //     .yAxisPadding(0.1)

    dc.renderAll();


    // var commitsTimeline2 = dc.lineChart("#brush-test");
    // commitsTimeline2
    //     .width(990)
    //     .height(50)
    //     .margins({
    //         : 15,
    //         right: 0,
    //         bottom: 20,
    //         left: 0
    //     })
    //     .dimension(weekDim)
    //     .group(weekGroup)
    //     .x(d3.time.scale().domain([dateRange.minWeek, dateRange.maxWeek]))
    //     .xUnits(d3.time.weeks)
    //     .round(d3.time.week.round)
    //     // .gap(1)
    //     // .centerBar(true)
    //     .interpolate("basis")

    // var margin = {
    //         top: 10,
    //         right: 10,
    //         bottom: 100,
    //         left: 40
    //     },
    //     width = 1160 - margin.left - margin.right,
    //     height = 220 - margin.top - margin.bottom;
    // //width = 950, height = 90;
    // var x = d3.time.scale().range([0, width]),
    //     y = d3.scale.linear().range([height, 0]);
    //
    //
    //
    // //Data Population
    // var xAxis = d3.axisBottom(x),
    //     yAxis = d3.axisLeft(y);
    //
    // leftBrush = d3.svg.brush()
    //     .x(x)
    //     .on("brushend", brushended)
    //     .extent(0,500);
    //
    // // rightBrush = d3.svg.brush()
    // //     .x(x)
    // //     .on("brushend", brushended);
    //
    // var area = d3.svg.area()
    //     .interpolate("monotone")
    //     .x(function(d) {
    //         return x(d.date);
    //     })
    //     .y0(height)
    //     .y1(function(d) {
    //         return y(d.ExamCount);
    //     });
    //
    // var svg = d3.select("#timeslider").append("svg")
    //     .attr("width", width + margin.left + margin.right)
    //     .attr("height", height + margin.top + margin.bottom)
    //     .append("g")
    //     .attr("transform", "translate(10,0)");
    //
    //
    // svg.append("defs").append("clipPath")
    //     .attr("id", "clip")
    //     .append("rect")
    //     .attr("width", width)
    //     .attr("height", height);
    //
    // data.forEach(function(d) {
    //     d.Date = parseDate(d.Date);
    //     d.ExamCount = +d.ExamCount;
    // });
    //
    // x.domain(d3.extent(data.map(function(d) {
    //     return d.Date;
    // })));
    // y.domain([0, d3.max(data.map(function(d) {
    //     return d.ExamCount;
    // }))]);
    //
    // var zoom = d3.behavior.zoom()
    //     .center([width / 2, height / 2])
    //     .scaleExtent([1, 100])
    //     .y(y)
    //     .x(x).on("zoom", function() {
    //         svg.select("path").attr("d", area);
    //         svg.select(".x.axis").call(xAxis);
    //     });
    //
    // svg.append("path")
    //     .datum(data)
    //     .attr("clip-path", "url(#clip)")
    //     .attr("d", area);
    //
    //
    // svg.append("g")
    //     .attr("class", "x brush")
    //     .call(brush.extent([ts_start, ts_end]))
    //     .selectAll("rect")
    //     .attr("height", height / 2)
    //     .style({
    //         "fill": " #ff0000",
    //         "fill-opacity": "0.8"
    //     });
    //
    // svg.append("g")
    //     .attr("transform", "translate(0," + height / 2 + ")")
    //     .attr("class", "x brush1")
    //     .call(brush1.extent([ts_start1, ts_end1]))
    //     .selectAll("rect")
    //     .attr("height", height / 2)
    //     .style({
    //         "fill": "#69f",
    //         "fill-opacity": "0.8"
    //     });
    //
    // svg.append("g")
    //
    // .attr("class", "y axis")
    //
    // svg.append("g")
    //     .attr("class", "x axis top")
    //     .attr("transform", "translate(0," + height + ")")
    //     .call(xAxis);
    //
    // svg.append("g")
    //     .attr("class", "y axis top")
    //     .call(yAxis);
    //
    // //Create Y axis label
    // svg.append("g")
    //     .attr("class", "y axis top")
    //     .call(yAxis)
    //     .append("text")
    //     .attr("transform", "rotate(-90)")
    //     .attr("y", 0)
    //     .attr("x", 0 - (height / 2))
    //     .attr("dy", "1em")
    //     .style("text-anchor", "middle")
    //     .text("Exam Count");
    //
    // // svg.call(zoom)
    // // .attr("transform","translate(40,0)scale(1,1)");;
    //
    // // });
    //
    //
    // var zoomed = function() {
    //     var trans = d3.event.translate;
    //     var scale = d3.event.scale;
    //
    //     svg.attr("transform",
    //         "translate(" + trans + ")" +
    //         " scale(" + scale + ")");
    // }
    //
    //
    // function brushended() {
    //     if (!d3.event.sourceEvent) return; // only transition after input
    //     var extent0 = brush.extent(),
    //         extent1 = extent0.map(d3.time.day.round);
    //     stDate = extent1[0];
    //     edDate = extent1[1];
    //     // if empty when rounded, use floor & ceil instead
    //     if (extent1[0] >= extent1[1]) {
    //         extent1[0] = d3.time.day.floor(extent0[0]);
    //         extent1[1] = d3.time.day.ceil(extent0[1]);
    //     }
    //
    //     var extent00 = brush1.extent(),
    //         extent10 = extent00.map(d3.time.day.round);
    //     stDate1 = extent10[0];
    //     edDate1 = extent10[1];
    //     // if empty when rounded, use floor & ceil instead
    //     if (extent10[0] >= extent10[1]) {
    //         extent10[0] = d3.time.day.floor(extent00[0]);
    //         extent10[1] = d3.time.day.ceil(extent00[1]);
    //     }
    //
    //     d3.select(this).transition()
    //         .call(brush.extent(extent1))
    //         .call(brush.event)
    //         .call(brush1.extent(extent10))
    //         .call(brush1.event);
    //
    //     var et = String(edDate).split(" ");
    //     var st = String(stDate).split(" ");
    //
    //     var et1 = String(edDate1).split(" ");
    //     var st1 = String(stDate1).split(" ");
    //     if (et.length > 2 && st.length > 2) {
    //         var months = {
    //             Jan: 1,
    //             Feb: 2,
    //             Mar: 3,
    //             Apr: 4,
    //             May: 5,
    //             Jun: 6,
    //             Jul: 7,
    //             Aug: 8,
    //             Sep: 9,
    //             Oct: 10,
    //             Nov: 11,
    //             Dec: 12
    //         };
    //         stDate = st[3] + ("0" + (months[st[1]])).slice(-2) + ("0" + et[2]).slice(-2);
    //         edDate = et[3] + ("0" + (months[et[1]])).slice(-2) + ("0" + et[2]).slice(-2);
    //         stDate1 = st1[3] + ("0" + (months[st1[1]])).slice(-2) + ("0" + st1[2]).slice(-2);
    //         edDate1 = et1[3] + ("0" + (months[et1[1]])).slice(-2) + ("0" + et1[2]).slice(-2);
    //     }
    //     $("#tsrange").text("Range:" + stDate + ": " + edDate);
    //     $("#tsrange").append("<br>Range:" + stDate1 + ": " + edDate1);
    // }

}
