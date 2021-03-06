var focus = null;
var authorKey = {};
var legendDrawn = false;
var packingData = null;
var PACKING_MODULES = {
  BUGS: 0,
  TEMPORAL_COUPLING: 1,
  CODE_AGE: 2,
  KNOWLEDGE_MAP: 3,
  FILE_INFO: 4
};
var mode = PACKING_MODULES.KNOWLEDGE_MAP;

var containerWidth = $("#packing-container").width();
var containerHeight = Math.floor($(window).height() * 0.90);//$("#packing-container").height();



console.log("packing container height: " + containerHeight);
console.log("packing container width: " + containerWidth);

var margin = 5,
  outerDiameter = Math.min(containerHeight, containerWidth),
  innerDiameter = outerDiameter - margin - margin;

var x = d3.scale.linear()
  .range([0, innerDiameter]);

var y = d3.scale.linear()
  .range([0, innerDiameter]);

var color = d3.scale.linear()
  .domain([-1, 5])
  .range(["hsl(185,60%,99%)", "hsl(187,40%,70%)"])
  .interpolate(d3.interpolateHcl);

var pack = d3.layout.pack()
  .padding(2)
  .size([innerDiameter, innerDiameter])
  .value(function(d) {
    return d.file_info.loc;
  });

var svg = d3.select("#packing-container").append("svg")
  .attr("width", outerDiameter)
  .attr("height", outerDiameter)
  .style("display", "block")
  .style("margin", "auto")
  .append("g")
  .attr("transform", "translate(" + margin + "," + margin + ")");

var tip = d3.tip()
  .attr('class', 'd3-tip')
  .offset([-10, 0])
  .html(function(d) {
    var baseHTML = "<strong style='font-size:18px'>" + d.name +
                   "</strong><br style='line-height:160%'/>"
    switch (mode) {
      case PACKING_MODULES.FILE_INFO:
        // Convert epoch times to dates
        if (!(d.file_info.creation_date instanceof moment)) {
          d.file_info.creation_date = moment(1000 * d.file_info.creation_date);
          d.file_info.last_modified = moment(1000 * d.file_info.last_modified);
        }
        return baseHTML + "<span>Lines of Code: " + d.file_info.loc + "</span>"
                        + "</br><span>Total Revisions: " + d.file_info.total_revisions
                        + "</span></br><span>Creation Date:  "
                        + d.file_info.creation_date.format("M/D/YY")
                        + "</span></br><span> Last Modified:  "
                        + d.file_info.last_modified.format("M/D/YY")
                        + "</span>"
      case PACKING_MODULES.BUGS:
        return baseHTML + "<span>Bug Score: </span><span style='color:red'>"
                        + Math.round(d.bug_info.score*100)/100 + "</span></br>"
                        + "<span>Number of Bugs: " + d.bug_info.count + "</span>";
      case PACKING_MODULES.TEMPORAL_COUPLING:
        var html = baseHTML + "<span>Temporal Coupling Score: </span>";
        if (d.tc_info.score > 0) {
          html += "<span style='color:red'>" + Math.round(d.tc_info.score*100)/100 +
                  "</span></br><span>Number of Revisions: " + d.tc_info.num_revisions + "</span>" +
                  "</span><br/><span>Coupled File: </span><span style='color:red'>"
                  + d.tc_info.coupled_module + "</span></br>" + "<span>Number of Mutual Revisions: "
                  + d.tc_info.num_mutual_revisions + "</span></br>" + "<span>Percent Coupled: </span>"
                  + "<span style='color:red'>" + Math.round(d.tc_info.percent*100) + "%</span>";
        } else {
          html += "<span>" + d.tc_info.score + "</span>";
        }
        return html;
      case PACKING_MODULES.KNOWLEDGE_MAP:
        var sorted_authors = [];
        for (var key in d.knowledge_info.top_authors) { sorted_authors.push([key, d.knowledge_info.top_authors[key]]); }
        sorted_authors.sort(function(a, b) { return b[1] - a[1]; })
        var html = baseHTML + "<strong>Top Contributors</strong>"
                            + "</br style='line-height:135%'><ul style='margin-bottom:0px;'>";
        for (var i in sorted_authors) {
          var author = sorted_authors[i]
          html += "<li><b style='color:" + authorKey[author[0]] + "'>" + author[0] + "</b> with<b> " + author[1] + "</b> changes</li>";
        }
        html += "</ul>";
        return html;
    }
  });

function drawLegend() {
  if (legendDrawn) {
    return;
  }

  var legendContainerWidth = $("#legend").width();
  var offsetX = 5;
  var offsetY = 5;
  var legendRectSize = 18;
  var legendSpacing = 4;
  var keyHeight = legendRectSize + legendSpacing;
  var colTextWidth = 160;
  var numKeys = Object.keys(authorKey).length;
  var keyWidth = colTextWidth + legendRectSize;
  var numCols = Math.floor(legendContainerWidth/keyWidth);
  var keysPerCol = Math.ceil(numKeys/numCols);

  var legendWidth = Math.ceil(numKeys/keysPerCol) * keyWidth + offsetX;
  var legendHeight = keysPerCol * keyHeight + offsetY;

  var legendSVG = d3.select("#legend").append("svg")
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    // .style('overflow', 'visible')
    .style('margin', 'auto')
    .style('display', 'block')
    .append("g")
    .attr("transform", "translate(" + offsetX + "," + offsetY + ")");
  var legend = legendSVG.selectAll('.legend')
        .data(Object.keys(authorKey))
        .enter()
        .append('g')
        .attr('class', 'legend')
        .attr('transform', function(d, i) {
          var col = Math.floor(i/keysPerCol);
          var row = i % keysPerCol;
          return "translate(" + col*keyWidth + "," + row*keyHeight + ")";
        });
  legend.append('rect')
    .attr('width', legendRectSize)
    .attr('height', legendRectSize)
    .style('fill', function(d){
      return authorKey[d];
    })
    .style('stroke', function(d){
      return authorKey[d];
    });
  legend.append('text')
    .attr('x', legendRectSize + legendSpacing)
    .attr('y', legendRectSize - legendSpacing)
    .style('fill', 'white')
    .style('font-size', '14px')
    .text(function(d) { return d; });
  legendDrawn = true;
}

function colorCircles() {
  $('#legend').hide();
  switch (mode) {
    case PACKING_MODULES.FILE_INFO:
      svg.selectAll("circle")
        .style("fill", function(d) {
          return d.children ? color(d.depth) : "WhiteSmoke";
        })
        .style("fill-opacity", function(d) {
          return d.children ? color(d.depth) : 1;
        });
        break;
    case PACKING_MODULES.BUGS:
      svg.selectAll("circle")
        .style("fill", function(d) {
          if (d.children) {
            return color(d.depth);
          } else {
            return d.bug_info.score > 0.0 ? "darkred" : "WhiteSmoke";
          }
        })
        .style("fill-opacity", function(d) {
          return d.children ? 1 : d.bug_info.opacity;
        });
        break;
    case PACKING_MODULES.TEMPORAL_COUPLING:
      svg.selectAll("circle")
        .style("fill", function(d) {
          if (d.children) {
            return color(d.depth);
          } else {
            return d.tc_info.color === null ? "WhiteSmoke" : d3.rgb(d.tc_info.color);
          }
        })
        .style("fill-opacity", function(d) {
          return d.children ? 1 : d.tc_info.color === null ? 0 : d.tc_info.opacity;
        });
        break;
    case PACKING_MODULES.KNOWLEDGE_MAP:
      svg.selectAll("circle")
        .style("fill", function(d) {
          if (d.children) {
            return color(d.depth);
          } else {
            if ((d.knowledge_info.color in authorKey) && (authorKey[d.knowledge_info.color] != d.knowledge_info.author)) {
              authorKey[d.knowledge_info.color] = "Other";
            } else {
              authorKey[d.knowledge_info.color] = d.knowledge_info.author;
            }
            return d3.rgb(d.knowledge_info.color);
          }
        })
        .style("fill-opacity", function(d) {
          return d.children ? color(d.depth) : 1;
        });
        // Reverse keys and values for D3 legend
        var reversed = {};
        for (var c in authorKey) {
          reversed[authorKey[c]] = c;
        }
        authorKey = reversed;
        drawLegend();
        $('#legend').show();
        break;
  }
}

function adjustLabels(k) {
    svg.selectAll("text")
        .style("opacity", function(d) {
            return k * d.r > 20 ? 1 : 0;
        })
        .text(function(d) {
            return d.name;
        })
        .filter(function(d) {
            d.tw = this.getComputedTextLength();
            return (Math.PI*(k*d.r)/2) < d.tw;
        })
        .each(function(d) {
            // Only truncate labels for child elements
            if (d.children) {
              d3.select(this).text(d.name);
              return;
            }
            var proposedLabel = d.name;
            var proposedLabelArray = proposedLabel.split('');
            while ((d.tw > (Math.PI*(k*d.r)/2) && proposedLabelArray.length)) {
                // pull out 3 chars at a time to speed things up (one at a time is too slow)
                proposedLabelArray.pop();proposedLabelArray.pop(); proposedLabelArray.pop();
                if (proposedLabelArray.length===0) {
                    proposedLabel = "";
                } else {
                    proposedLabel = proposedLabelArray.join('') + "..."; // manually truncate with ellipsis
                }
                d3.select(this).text(proposedLabel);
                d.tw = this.getComputedTextLength();
            }
        });
}

function zoom(d, i) {
  // Do not allow leafs to zoom
  if(!d.children) { d = d.parent; }

  var focus0 = focus;
  focus = d;
  var updateCounter = 0;

  var k = innerDiameter / d.r / 2;
  x.domain([d.x - d.r, d.x + d.r]);
  y.domain([d.y - d.r, d.y + d.r]);

  var transition = svg.selectAll("text,circle").transition()
    .duration(d3.event.altKey ? 7500 : 750)
    .attr("transform", function(d) {
      return "translate(" + x(d.x) + "," + y(d.y) + ")";
    });

  transition.filter("circle")
    .attr("r", function(d) {
      return k * d.r;
    });

  transition.filter("text")
    .style("opacity", 0)
    .filter(function(d) {
      return d.parent === focus || d.parent === focus0;
    })
    .style("fill-opacity", function(d) {
      return d.parent === focus ? 1 : 0;
    })
    .each("start", function(d, i) {
      if (d.parent === focus) this.style.display = "inline";
      this.style.opacity = 0;
      updateCounter++;
    })
    .each("end", function(d, i) {
      if (d.parent !== focus) this.style.display = "none";
      updateCounter--;
      if (updateCounter == 0) {
        adjustLabels(k);
      }
    });

  d3.event.stopPropagation();
}

function buildViz(requestUrl) {
  d3.json(requestUrl, function(error, root) {
    root = JSON.parse(root);
    packingData = root;
    focus = root,
      nodes = pack.nodes(root);

    // DEBUG
    console.log(root);

    svg.append("g").selectAll("circle")
      .data(nodes)
      .enter().append("circle")
      .attr("class", function(d) {
        return d.parent ? d.children ? "node" : "node node--leaf" : "node node--root";
      })
      .attr("transform", function(d) {
        return "translate(" + d.x + "," + d.y + ")";
      })
      .attr("r", function(d) {
        return d.r;
      })
      .on("click", function(d) {
        return zoom(focus == d ? root : d);
      });

    svg.append("g").selectAll("text")
      .data(nodes)
      .enter().append("text")
      .attr("class", "label")
      .attr("transform", function(d) {
        return "translate(" + d.x + "," + d.y + ")";
      })
      .style("fill-opacity", function(d) {
        return d.parent === root ? 1 : 0;
      })
      .style("display", function(d) {
        return d.parent === root ? null : "none";
      })
      .style("opacity", function(d) {
        return d.r > 20 ? 1 : 0;
      })
      .style("font-weight", function(d) {
        return d.children ? "bold" : "normal";
      })
      .text(function(d) {
        return d.name;
      });

    svg.call(tip);

    svg.selectAll(".node--leaf")
      .on('mouseover', tip.show)
      .on('mouseout', tip.hide);

    colorCircles(mode);
    $(".loader-mask").fadeOut(250);
    $(".loader").fadeOut(500);
  });

  d3.select(self.frameElement).style("height", outerDiameter + "px");
}

function bindButtons() {
  $('#temp-coup-btn').on('click', function(e) {
    mode = PACKING_MODULES.TEMPORAL_COUPLING;
    colorCircles();
  });
  $('#bugs-btn').on('click', function(e) {
    mode = PACKING_MODULES.BUGS;
    colorCircles();
  });
  $('#file-info-btn').on('click', function(e) {
    mode = PACKING_MODULES.FILE_INFO;
    colorCircles();
  });
  $('#knowledge-map-btn').on('click', function(e) {
    mode = PACKING_MODULES.KNOWLEDGE_MAP;
    colorCircles();
  });
}
