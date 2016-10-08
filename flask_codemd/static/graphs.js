


function buildGraphs(commitsJson, filesJson) {
  // Clean commits data; convert dates from unix timestamps to js dates
  commitsJson.forEach(function(d) {
    d['date'] = new Date(d['date'] * 1000);
  });

  var dateFormat = d3.time.format("%x");

  var commits = crossfilter(commitsJson);
  var dateDim = commits.dimension(function(d){ return dateFormat(d['date']); });
  var revisionIdDim = commits.dimension(function(d){ return d['revision_id']; });

  var files = crossfilter(filesJson);
  var insertionsDim = files.dimension(function(d) { return d['insertions']; });
  var deletionsDim = files.dimension(function(d) { return d['deletions']; });
  var linesDim = files.dimension(function(d) { return d['lines']; });

  // Aggregated values
  var numCommitsByDate = dateDim.group();

  // Build graphs
  var timeChart = dc.barChart("#time-chart");

  timeChart
		.width(600)
		.height(160)
		.margins({top: 10, right: 50, bottom: 30, left: 50})
		.dimension(dateDim)
		.group(numCommitsByDate)
		.transitionDuration(500)
		.x(d3.time.scale().domain([minDate, maxDate]))
		.elasticY(true)
		.xAxisLabel("Day")
		.yAxis().ticks(4);

    dc.renderAll();
}
