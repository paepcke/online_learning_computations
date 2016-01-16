"use strict"
/*
 * TODO:
 *     o Add 'testing' as a param for instance creation?
 *     o Add optional callback function to subscribeToTopic() 
 *     

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
 *    course(string)          Medicine/HRP258/Statistics_in_Medicine
 *    learner(string),        55e906bd8d133cef1975080aa2bf8ff142bb1d6a
 *    percentGrade(float),    30.0
 *    attempts(int),          1
 *    firstSubmit(datetime),  2013-05-13 12:38:30
 *    lastSubmit(datetime),   2013-05-13 12:42:37 
 *    probId(string)          i4x://Medicine/HRP258/problem/e252cc0b13b146c1805a90cf45aa376b
 * 
 * Underlying query:
 * 
 * 
 *     (SELECT 'course','learner','grade','attempts','firstSubmit','lastSubmit','probId')
 *     UNION
 *     (SELECT course_display_name AS course,
 *     	    anon_screen_name AS learner,
 *    	    percent_grade AS percentGrade,
 *    	    num_attempts AS attempts,
 *    	    first_submit AS firstSubmit,
 *    	    last_submit AS lastSubmit,
 *    	    module_id AS probId
 *      INTO OUTFILE '/tmp/cs145Grades.csv'
 *      FIELDS TERMINATED BY "," OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n'
 *      FROM ActivityGrade
 *      WHERE course_display_name = 'Engineering/db/2014_1'
 *        AND num_attempts > -1)
 *      ORDER BY firstSubmit;
 * 
 */

var testTuples = [
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "3e43611e9969f85c5354894e66822434a7ee61d8",
				    "percentGrade" : 30.0,
				    "attempts" : 2,
				    "firstSubmit" : "2013-06-11 15:15:08",
				    "lastSubmit" : "2013-07-16 06:43:23",
				    "probId" : "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
				   },
/*				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "6a6c70f0f9672ca4a3e16bdb5407af51cd18e4e5",
				    "percentTrade" : 10.0,
				    "attempts" : 1,
				    "firstSubmit" : "2013-06-11 15:12:13",
				    "lastSubmit" : "2013-07-07 00:10:51",
				    "probId" : "i4x://Medicine/HRP258/problem/5542da143b054d0ba3efdb243b5eb343"
				   },
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "cb2bb63c14e6f5fc8d21b5f43c8fe412c7c64c39",
				    "percentGrade" : 100.0,
				    "attempts" : 1,
				    "firstSubmit" : "2013-06-11 15:21:11",
				    "lastSubmit" : "2013-07-1506:13:51",
				    "probId" : "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
				   }
*/                  ];

var TESTING = false;

function gradeCharter() {

	/************************** Instance Variables ********************/

	if (typeof my !== 'undefined') {
		throw "Please obtain the gradeCharter instance via gradeCharter.getInstance()." 
	}
	
	// Make a private object in which we'll 
	// stick instance vars and private methods:
	var my = {};

	// No singleton instance yet:
	my.instance = null;
	
	//****my.outerWidth = 960,
	my.outerWidth = 500,
	my.outerHeight = 500,
	my.margin = {top: 10, right: 10, bottom: 10, left: 10},
	//****my.margin = {top: 0, right: 0, bottom: 0, left: 0},
	my.padding = {top: 10, right: 10, bottom: 10, left: 10},
	//****my.padding = {top: 10, right: 10, bottom: 10, left: 10},
	my.xLabelsHeight = 35,
	my.yLabelsWidth  = 20,
	my.xAxisTitleHeight = 20,
	my.yAxisTitleWidth = 30,
	my.innerWidth = my.outerWidth - my.margin.left - my.margin.right - my.yLabelsWidth - my.yAxisTitleWidth,
	my.innerHeight = my.outerHeight - my.margin.top - my.margin.bottom - my.xLabelsHeight - my.xAxisTitleHeight,
	my.chartWidth = my.innerWidth - my.padding.left - my.padding.right,
	my.chartHeight = my.innerHeight - my.padding.top - my.padding.bottom,
	my.chartOriginX = my.margin.left + my.padding.left + my.yLabelsWidth + my.yAxisTitleWidth,
	my.chartOriginY = my.chartHeight,
	my.xTitleOriginX = my.chartOriginX + my.chartWidth / 2,
	my.xTitleOriginY = my.chartHeight + my.xLabelsHeight,
	my.yTitleOriginX = my.chartOriginX - my.yAxisTitleWidth,
	my.yTitleOriginY = my.chartHeight - my.chartHeight/2;
	
	//my.transitionDuration = 1500;
	my.transitionDuration = 500;
	
	my.svg;
	my.xScale;
	my.yScale;
	my.xAxis;
	my.yAxis;
	
	// Dict probId-->stats about that problem:
	//     probStats[probId] -> {'numAttempts' : <m>,
    //                           'num1stSuccesses : <n>			
	//							 'successRate' : <o>,
	//                          }
	my.probStats = {};
	// Problem IDs, time ordered (if data was delivered time-sorted!):
	my.probIdArr = [];
	// Number of times the most frequently taken problem was taken:
	my.maxNumTakers  = 0;
	// Map probId-->number of learners who got the problem on the first try:
	my.probNum1stSuccess = {};
	
		
	/************************** Initialization ********************/
	
	
	/*-----------------------
	 * init
	 *-------------*/
	my.init= function() {
		
		my.svg = d3.select("body").append("svg")
			  		 .attr("class", "gradechart")
			  		 .attr("id", "gradechart")
			  		 .attr("width", my.outerWidth)
			  		 .attr("height", my.outerHeight)
					 .append("g")
					 .attr("transform", "translate(" + my.margin.left + "," + my.margin.top + ")");
		
		
		my.xScale = d3.scale.ordinal()
		    .rangeRoundBands([my.chartOriginX, my.chartWidth], .2,.1);		
		
		my.yScale = d3.scale.linear()
			// Domain will be set when the y axis is rescaled.
		    .range([my.chartOriginY, my.margin.top + my.padding.top]);
		
		my.createAxes(my.xScale, my.yScale);
	}
	
	/************************** Public Methods ********************/

	/*-----------------------
	 * getInstance
	 *-------------*/
	
	my.getInstance = function() {
		return my.instance;
	}
	
	/*-----------------------
	 * updateViz
	 *-------------*/
	
	my.updateViz = function(gradeObjs) {
		/*
		 * Public method called when a new set of grade info 
		 * tuples arrives. The expected format is an
		 * array of objects:
		 * It is OK to to have additional fields in these
		 * objects; they are ignored. 
		 * 
		 *	  [
		 *	     { "course" : "Medicine/HRP258/Statistics_in_Medicine",
		 *	       "probId" : "i4x://Medicine/HRP258/problem/5542da143b054d0ba3efdb243b5eb343",
		 *		   "firstSubmit": "2013-06-11 15:12:13",
		 *		   "attempts": "1"
		 *       },
		 *		   ...
		 *	  ]
 		 * 
		 */
		
		if (!my.isArray(gradeObjs) || gradeObjs.length === 0) {
			return;
		}
		// Update the internal record of the data:
		var newProbGradeObjs = my.updateDataRepAndScales(gradeObjs);

		// Update height of existing bars, and add
		// new ones as needed:
		
		// Data is array of problem ids for *all*
		// problems seen so far, in time order:
		var gradeBars = my.svg.selectAll(".gradebar")
		    	 .data(my.probIdArr);

		// UPDATE existing rects: nothing special to do
		//        for them.

		// ENTER new rectangles for the never-seen problems:
		gradeBars.enter()
		    	 .append("rect")
		    	 .attr("class", "gradebar")
		    	 .attr("id", function(probId) {
		    		 return probId;
		    	 });
		    	 
	    // Both new and old rects: update sizes
		// and locations on X-axis:
				    	// Place this rectangle object by the probId
				    	// it represents:
		 gradeBars.attr("x", function(probId) {
						return my.xScale(probId);
						})
				  .attr("y", function(probId) {
						// How many attempts did his problem id take in 
						// total across all learner?
						var numTakers =  my.probStats[probId];
						return my.yScale(numTakers);
					 	})
				  .attr("width", my.xScale.rangeBand())
				  .attr("height", function(probId) {
						var numTakers = my.probStats[probId];
						return my.chartHeight - my.yScale(numTakers);
					 	})
				  .transition().duration(my.transitionDuration)
				  .style("opacity", 1);

		my.rescaleAxes();
		
	}
	
	/************************** Private Methods ********************/
	
	/*-----------------------
	 * updateDataRepAndScales
	 *-------------*/

	my.updateDataRepAndScales = function(gradeObjs) {
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
		 * Returns a new array that only contains gradeObjs
		 * for problems we have not seen before.
		 * 
		 * Relies on caller to ensure that gradeObjs is an
		 * array of objects.
		 * 
		 * :param gradeObjs: is a an array of all information 
		 *         associated with a grade, such as learner ID,
		 *         course, number of attempts, grade, etc. Though
		 *         currently only "probId" and "attempts" are
		 *         used.
		 * :type gradeObjs: [{}]
		 * :return: array of gradeObj for problems for which we haven't had
		 *      information delivered.
		 * :rType: [{}]
		 */
		
		var newProblemObjs = [];
		for (var i=0, len=gradeObjs.length; i<len; i++) {
			var gradeObj = gradeObjs[i];
			var probId = gradeObj["probId"];
			var numAttempts = parseInt(gradeObj["attempts"]);
			if (isNaN(numAttempts)) {
				continue;
			}
			if (typeof my.probStats[probId] === 'undefined') {
				// Got a problem ID we've never seen;
				// remember that this new problem had
				// nobody take it yet:
				my.probStats[probId] = numAttempts;
				my.probIdArr.push(probId);
				// How often this problem was successfully taken
				// with one tey:
				my.probNum1stSuccess[probId] = 0;
				// Remember the info about this new problem:
				newProblemObjs.push(gradeObj);
				var haveNewProbId = true;
			} else {
				my.probStats[probId] += numAttempts;
			}
			
			// Update largest number of takers among all problems
			// (i.e. the highest Y-value:
			if (my.probStats[probId] > my.maxNumTakers) {
				my.maxNumTakers = my.probStats[probId];
			}
			
			// For this problem: update the number of
			// learners who got the problem on the first try:
			if (numAttempts == 1) {
				my.probNum1stSuccess[probId] += 1;
			}
		}

		if (haveNewProbId) {
			my.xScale.domain(my.probIdArr);
			// Update the my.xAxis labels: this
			// function will be called with
			// d being one problem ID. The func
			// must return a corresponding x Axis label.
			// We just label with the problem's sequence
			// number. The '+1' is to make the counting
			// 1-based: first problem is 1:
			my.xAxis.tickFormat(function(d) {
						return my.probIdArr.indexOf(d) + 1;
						})
		}

		my.yScale.domain([0, my.maxNumTakers]);
		return newProblemObjs;
	}
	
	/*-----------------------
	 * rescaleAxes
	 *-------------*/

	my.rescaleAxes = function() {
		my.svg.select("#xAxisGroup")
			.transition().duration(my.transitionDuration)
			.call(my.xAxis);
		my.svg.select("#yAxisGroup")
			.transition().duration(my.transitionDuration)
			.call(my.yAxis);
		
		// Move the axis Titles:
		if (my.xScale.domain().length > 0) {
			// At least one problem bar exists. Find the middle
			// of all the problem bars:
			var xAxisMidpoint = my.computeXTitleMidpoint();
			my.svg.select("#xAxisTitle")
				.transition().duration(my.transitionDuration)
				.attr("transform", "translate(" + xAxisMidpoint + "," + my.xTitleOriginY + ")")
		}
		if (my.yScale.domain().length > 0) {
			var yAxisMidpoint = my.computeYTitleMidpoint();
			my.svg.select("#yAxisTitle")
				.transition().duration(my.transitionDuration)
				.attr("transform", "translate(" + my.yTitleOriginX + "," + yAxisMidpoint + "),rotate(-90)")
		}
	}
	
	/*-----------------------
	 * computeXTitleMidpoint
	 *-------------*/
	
	my.computeXTitleMidpoint = function() {
		
		var xPoints = my.xScale.domain();
		var numXPoints = xPoints.length;
		if (numXPoints == 0) {
			return my.xTitleOriginX;
		} else if (numXPoints == 1) {
			// Middle of X title is under
			// the one and only bar, plus half
			// a bar width:
			return my.xScale(xPoints[0]) + my.xScale.rangeBand()/2;
		}
		// Got at least two points on the X axis.
		// If an even number, get positions of
		// ticks on right and left of mid point,
		// and interpolate. Else take the x position
		// of the middle tick:
		if (numXPoints % 2 == 0) {
			// Even number of x-ticks; get pixel address 
			// of points on left and right of the middle:
			var left  = my.xScale(xPoints[numXPoints/2 - 1]);
			var right = my.xScale(xPoints[numXPoints/2]);
			// Interpolate between the left and right point,
			// and add half a bar width, b/c scale addresses
			// are to the lower left edge of a bar:
			return left + (right - left)/2  + my.xScale.rangeBand()/2;
		} else {
			// Odd number of x ticks:
			return my.xScale(xPoints[Math.ceil(numXPoints/2)])  + my.xScale.rangeBand()/2;
		}
	}

	/*-----------------------
	 * computeYTitleMidpoint
	 *-------------*/
	
	my.computeYTitleMidpoint = function() {
		
		var yPoints = my.yScale.domain();
		var numYPoints = yPoints.length;
		if (numYPoints == 0) {
			return my.yTitleOriginX;
		} else if (numYPoints == 1) {
			// Middle of Y title is next to
			// the one and only labeled tick:
			return my.yScale(yPoints[0]);
		}
		// Got at least two labeled ticks on the Y axis.
		// If an even number, get positions of
		// ticks on top and bottom of mid point,
		// and interpolate. Else take the y position
		// of the middle tick:
		if (numYPoints % 2 == 0) {
			// Even number of y-ticks; get y-pixel address 
			// of points top and bottom of the middle:
			var bottom  = my.yScale(yPoints[numYPoints/2 - 1]);
			var top = my.yScale(yPoints[numYPoints/2]);
			// Interpolate between the bottom and top point,
			return bottom - (bottom-top)/2;
		} else {
			// Odd number of y ticks:
			return my.yScale(yPoints[Math.ceil(numYPoints/2)]);
		}
	}
	
	/*-----------------------
	 * createAxes
	 *-------------*/
	
	my.createAxes = function(theXScale, theYScale) {
		
		my.xAxis = d3.svg.axis()
					   .scale(theXScale)
					   .orient("bottom");
        my.yAxis = d3.svg.axis()
        			  .scale(theYScale)
        			  .orient("left");

        my.svg.append("g")
			.attr("id", "xAxisGroup")
			.attr("class", "axis")
			.attr("transform", "translate(0, " + my.chartHeight + ")")
			.call(my.xAxis)

		my.svg.append("g")
			.attr("id", "yAxisGroup")
			.attr("class", "axis")
			.attr("transform", "translate(" + my.chartOriginX + ", 0)")
			.call(my.yAxis)
						
		// Axis titles --- X axis:
		my.svg.append("text")
		    .attr("class", "axisTitle")
		    .attr("id", "xAxisTitle")
		    .attr("text-anchor", "middle")
		    .attr("transform", "translate(" + my.xTitleOriginX + "," + my.xTitleOriginY + ")")
		    .text("Assignments");
		my.svg.append("text")
		    .attr("class", "axisTitle")
		    .attr("id", "yAxisTitle")
		    .attr("text-anchor", "middle")
		    .attr("transform", "translate(" + my.yTitleOriginX + "," + my.yTitleOriginY + "), rotate(-90)")
		    .text("Number of learners");
		
	}
	

	/*-----------------------
	 * isArray
	 *-------------*/
	
	my.isArray = function(maybeArr) {
		/**
		 * Returns true if given item is an array.
		 * Else returns false.
		 */
		return Object.prototype.toString.call( maybeArr ) === '[object Array]';
	}
	
	/************************** Top-Level Statements ********************/
	
	// Make the object we'll actually return:
	var that = {}
	// Add a reference to the public ones of the above methods:
	that.getInstance = my.getInstance;
	that.updateViz   = my.updateViz;
	
	// Call the init function once for setup:
	my.init();
	my.instance = that;
	
	gradeCharter.getInstance = my.getInstance;
	
	// If this function wasn't a singleton,
	// we would now return 'that'. But 
	// callers must use gradeCharter.getInstance():
	return null;
}

// Initialize everything once:
gradeCharter();

if (TESTING) {
	var vizzer = gradeCharter.getInstance();
	vizzer.updateViz(testTuples);
	setTimeout(function() {
		var nextData = [
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
}
