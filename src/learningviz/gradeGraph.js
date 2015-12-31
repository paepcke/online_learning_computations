/*
 * Receive tuples of grades from a WebSocket, and
 * visualize in a browser window. The viz will 
 * continuously update. The tuples are expected to
 * be fed in order of learners' first-submission date.
 * If this assumption is violated, the bars in the
 * viz will not be ordered by the release sequence
 * of the course assignments.
 * 
 * We expect the following tuple format:
 *  
 *         Schema Column                     Example
 *    course_display_name(string)      Medicine/HRP258/Statistics_in_Medicine
 *    anon_screen_name(string),        55e906bd8d133cef1975080aa2bf8ff142bb1d6a
 *    grade(int),                      2
 *    num_attempts(int),               1
 *    first_submit(datetime),          2013-05-13 12:38:30
 *    last_submit(datetime),           2013-05-13 12:42:37 
 *    module_id(string)                i4x://Medicine/HRP258/problem/e252cc0b13b146c1805a90cf45aa376b
 * 
 * Underlying query:
 * 
 *     SELECT course_display_name, 
 *            anon_screen_name, 
 *            grade, 
 *            num_attempts, 
 *            first_submit, 
 *            last_submit, 
 *            module_id 
 *     FROM ActivityGrade 
 *     WHERE module_type = "problem" 
 *       AND num_attempts >= 1
 *     ORDER BY first_submit;
 *     
 *  To find the number of assignments ahead of time:
 *  
 *     SELECT COUNT(DISTINCT module_id) 
 *       FROM ActivityGrade 
 *      WHERE course_display_name = "Medicine/HRP258/Statistics_in_Medicine";
 */

var testTuples = [
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "3e43611e9969f85c5354894e66822434a7ee61d8",
				    "grade" : 5,
				    "attempts" : 2,
				    "firstSubmit" : "2013-06-11 15:15:08",
				    "lastSubmit" : "2013-07-16 06:43:23",
				    "probId" : "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
				   },
/*				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "6a6c70f0f9672ca4a3e16bdb5407af51cd18e4e5",
				    "grade" : 10,
				    "attempts" : 1,
				    "firstSubmit" : "2013-06-11 15:12:13",
				    "lastSubmit" : "2013-07-07 00:10:51",
				    "probId" : "i4x://Medicine/HRP258/problem/5542da143b054d0ba3efdb243b5eb343"
				   },
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "cb2bb63c14e6f5fc8d21b5f43c8fe412c7c64c39",
				    "grade" : 7,
				    "attempts" : 1,
				    "firstSubmit" : "2013-06-11 15:21:11",
				    "lastSubmit" : "2013-07-1506:13:51",
				    "probId" : "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
				   }
*/                  ];

function GradeCharter() {

	/************************** Instance Variables ********************/	
	var that = this;

	
	var outerWidth = 960,
	    outerHeight = 500,
	    //****margin = {top: 20, right: 20, bottom: 20, left: 20},
	    margin = {top: 0, right: 0, bottom: 0, left: 0},
	    //****padding = {top: 60, right: 60, bottom: 60, left: 60},
	    padding = {top: 10, right: 10, bottom: 10, left: 10},
	    xLabelsHeight = 35,
	    yLabelsWidth  = 20,
	    xAxisTitleHeight = 20,
	    yAxisTitleWidth = 30,
	    innerWidth = outerWidth - margin.left - margin.right - yLabelsWidth - yAxisTitleWidth,
	    innerHeight = outerHeight - margin.top - margin.bottom - xLabelsHeight - xAxisTitleHeight,
		chartWidth = innerWidth - padding.left - padding.right,
	    chartHeight = innerHeight - padding.top - padding.bottom,
		chartOriginX = margin.left + padding.left + yLabelsWidth + yAxisTitleWidth,
	    chartOriginY = chartHeight,
	    xTitleOriginX = chartOriginX + chartWidth / 2,
	    xTitleOriginY = chartHeight + xLabelsHeight,
	    yTitleOriginX = chartOriginX - yAxisTitleWidth,
	    yTitleOriginY = chartHeight - chartHeight/2;
	
	var transitionDuration = 3000;
	
	var svg;
	var xScale;
	var yScale;
	var xAxis;
	var yAxis;
	
	var probNumTakes = {};
	var probIdArr = [];
	var maxNumTakers  = 0;	
		
	/************************** Initialization ********************/
	
	
	this.init= function() {
		
		svg = d3.select("body").append("svg")
			  		 .attr("class", "gradechart")
			  		 .attr("width", outerWidth)
			  		 .attr("height", outerHeight)
					 .append("g")
					 .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
		
		
		xScale = d3.scale.ordinal()
		    .rangeRoundBands([chartOriginX, chartWidth], .2,.5);		
		
		yScale = d3.scale.linear()
			// Domain will be set when the y axis is rescaled.
		    .range([chartOriginY, margin.top + padding.top]);
		
		this.createAxes(xScale, yScale);
	}
	
	/************************** Public Methods ********************/
	
	GradeCharter.prototype.updateViz = function(gradeObjs) {
		/*
		 * Public method called when a new set of grade info 
		 * tuples arrives.
		 */
		
		// Update the internal record of the data:
		this.updateDataRepAndScales(gradeObjs);
		
		// Update height of existing bars, and add
		// new ones as needed:
		
		var gradeBars = svg.selectAll("rect")
		
		    	.data(gradeObjs, function(d) {
		    			// Return the tuple's problemId as
		    			// unique identifier:
		    			return d["probId"];
		    	 })
		    	
		    	// Updates of existing bars:
		    	 
   	    	   .transition().duration(transitionDuration)

		    	 
		    	.attr("x", function(d) {
		    		return xScale(d["probId"])
 		    	 })
				.attr("y", function(d) {
					var numTakers =  probNumTakes[d["probId"]];
		    		return yScale(numTakers);
		    	 })
		    	.attr("width", xScale.rangeBand())
		    	.attr("height", function(d) {
		    		return chartHeight - yScale(probNumTakes[d["probId"]]);
		    	 })
		    	
		    	// Done updating existing grade bars.
		    	// Now add bars for any new problems that
		    	// were delivered.
		    	.enter()
				
		    	// Add elements for the new data: 
		    	.append("rect")
		    	.style("opacity", 0)
				.attr("x", function(d) {
					probId = d["probId"];
					// Name this rectangle object by the probId
					// it represents:
					this.setAttribute("id", probId);
					this.setAttribute("class", "gradebar")
					return xScale(probId);
				})
				.attr("y", function(d) {
					// Another learner to incorporate into the chart.
					// How many attempts did his problem id take in 
					// total across all learner?
					var numTakers =  probNumTakes[d["probId"]];
					return yScale(numTakers);
				 })
				.attr("width", xScale.rangeBand())
				.attr("height", function(d) {
					var probId = d["probId"];
					var numTakers = probNumTakes[probId];
					return chartHeight - yScale(numTakers);
				 })
				.transition().duration(transitionDuration)
				.style("opacity", 1);
		this.rescaleAxes();
	}
	
	/************************** Private Methods ********************/
	
	/*-----------------------
	 * rescaleAxes
	 *-------------*/

	this.rescaleAxes = function() {
		//*****svg.select("#xAxisGroup").call(xAxis);
		svg.select("#xAxisGroup")
			.transition()
			.duration(transitionDuration)
			.call(xAxis);
		//****svg.select("#yAxisGroup").call(yAxis);
		svg.select("#yAxisGroup")
			.transition()
			.duration(transitionDuration)
			.call(yAxis);
	}
	
	/*-----------------------
	 * createAxes
	 *-------------*/
	
	this.createAxes = function(xScale, yScale) {
		
		xAxis = d3.svg.axis()
					   .scale(xScale)
					   .orient("bottom");
        yAxis = d3.svg.axis()
        			  .scale(yScale)
        			  .orient("left");

        svg.append("g")
			.attr("id", "xAxisGroup")
			.attr("class", "axis")
			.attr("transform", "translate(0, " + chartHeight + ")")
			.call(xAxis)

		svg.append("g")
			.attr("id", "yAxisGroup")
			.attr("class", "axis")
			.attr("transform", "translate(" + chartOriginX + ", 0)")
			.call(yAxis)
						
		// Axis titles --- X axis:
		svg.append("text")
		    .attr("class", "axisTitle")
		    .attr("text-anchor", "middle")
		    .attr("transform", "translate(" + xTitleOriginX + "," + xTitleOriginY + ")")
		    .text("Assignments");
		svg.append("text")
		    .attr("class", "axisTitle")
		    .attr("text-anchor", "middle")
		    .attr("transform", "translate(" + yTitleOriginX + "," + yTitleOriginY + "), rotate(-90)")
		    .text("Number of learners");
		
	}
	
	/*-----------------------
	 * updateDataRepAndScales
	 *-------------*/

	this.updateDataRepAndScales = function(gradeObjs) {
		/**
		 * Given incoming array of grade objects, go through
		 * each object and update our records of how many
		 * attempts each problem received so far. We also
		 * update the maximum number of attempts that any problem
		 * received, and the array of all problem ids.
		 * 
		 * Finally, we update the x and y scales to accommodate
		 * (possibly) new problem bars and y-axis heights.
		 * 
		 * :param gradeObjs: is a an array of all information 
		 *         associated with a grade, such as learner ID,
		 *         course, number of attempts, grade, etc.
		 * :type gradeObjs: [{}]
		 */
		
		for (var i=0, len=gradeObjs.length; i<len; i++) {
			var gradeObj = gradeObjs[i];
			var probId = gradeObj["probId"];
			var numAttempts = gradeObj["attempts"];
			if (typeof probNumTakes[probId] === 'undefined') {
				// Got a problem ID we've never seen;
				// remember that this new problem had
				// nobody take it yet:
				probNumTakes[probId] = numAttempts;
				probIdArr.push(probId);
				haveNewProbId = true;
			} else {
				probNumTakes[probId] += numAttempts;
			}
			if (probNumTakes[probId] > maxNumTakers) {
				maxNumTakers = probNumTakes[probId];
			}
		}

		if (haveNewProbId) {
			xScale.domain(probIdArr);
			// Update the xAxis labels: this
			// function will be called with
			// d being one problem ID. The func
			// must return a corresponding x Axis label.
			// We just label with the problem's sequence
			// number. The '+1' is to make the counting
			// 1-based: first problem is 1:
			xAxis.tickFormat(function(d) {
						return probIdArr.indexOf(d) + 1;
						})
		}

		yScale.domain([0, maxNumTakers]);
	}
	
	// Call the init function once for setup:
	this.init();
}

vizzer = new GradeCharter();

vizzer.updateViz(testTuples);
setTimeout(function() {
	nextData = [
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "6a6c70f0f9672ca4a3e16bdb5407af51cd18e4e5",
				    "grade" : 10,
				    "attempts" : 1,
				    "firstSubmit" : "2013-06-11 15:12:13",
				    "lastSubmit" : "2013-07-07 00:10:51",
				    "probId" : "i4x://Medicine/HRP258/problem/5542da143b054d0ba3efdb243b5eb343"
				   },
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "cb2bb63c14e6f5fc8d21b5f43c8fe412c7c64c39",
				    "grade" : 7,
				    "attempts" : 1,
				    "firstSubmit" : "2013-06-11 15:21:11",
				    "lastSubmit" : "2013-07-1506:13:51",
				    "probId" : "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
				   }
	            ];
	vizzer.updateViz(nextData)
	}, 3000);


