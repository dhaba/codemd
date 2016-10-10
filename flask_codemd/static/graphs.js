function buildGraphs(data) {
    // console.log(data)
    $("#json-data").html(data);
    // Clean commits data; convert dates from unix timestamps to js dates
    var commits_json = JSON.parse(data);
    var dateFormat = d3.time.format("%x");
    commits_json.forEach(function(d) {
        d.date = new Date(d.date * 1000);
    });


    var commits = crossfilter(commits_json);

    var dateDim = commits.dimension(function(d) { return d3.time.week(d.date); });
    var deletionDim = commits.dimension(function(d) { return d.deletions; });
    var insertionsDim = commits.dimension(function(d) { return d.insertions; });
    var netLinesDim = commits.dimension(function(d) { return d.insertions - d.deletions; })


    // Aggregated metrics
    var numCommitsByDate = dateDim.group();

    //Define values (to be used in charts)
    var minDate = dateDim.bottom(1)[0].date;
    var maxDate = dateDim.top(1)[0].date;

    console.log('min date: ' + minDate);
    console.log('max date ' + maxDate);

    // Build graphs
    var timeChart = dc.barChart("#time-chart");
    timeChart
        .width(600)
        .height(160)
        .margins({
            top: 10,
            right: 25,
            bottom: 35,
            left: 25
        })
        .dimension(dateDim)
        .group(numCommitsByDate)
        .transitionDuration(500)
        .x(d3.time.scale()) //.x(d3.time.scale().domain([minDate, maxDate]))
        .elasticX(true)
        .xUnits(d3.time.weeks)
        .elasticY(true)
        .xAxisLabel("Commits By Week")
        .yAxis().ticks(4);

    dc.renderAll();
}





// var map_func = function() {
//   this.files_modified.forEach(function(file) {
//     var key = this.date;
//     var value = {'insertions': file.insertions, 'deletions': file.deltions, 'lines': file.lines};
//     emit(key, value);
//   });
// };
//
// var reduce_fuc = function(date, ) {
//   reducedVal =
// };
//
//
// files_modified.append({'filename': file_name, \
//                                'insertions':file_mods['insertions'], \
//                                'deletions':file_mods['deletions'],
//                                'lines':file_mods['lines']})
