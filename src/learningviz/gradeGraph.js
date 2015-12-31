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
	
	/************************** Initialization ********************/
	
	
	var that = this;

	this.gradeCharter = function() {
		
/*		that.svgW = 900;
		that.svgH = 100;
		that.vertScale = 5;
		that.xAxisPad = 20;
		that.yAxisPad = 20;
*/		
		that.barGap = 4;
		that.margin = {top: 20, right: 20, bottom: 20, left: 20};
		that.padding = {top: 10, right: 10, bottom: 10, left: 10};
		that.outerWidth = 900;
		that.outerHeight = 100;
		that.innerWidth = that.outerWidth - that.margin.left - that.margin.right;
		that.innerHeight = that.outerHeight - that.margin.top - that.margin.bottom;
		that.svgW= that.innerWidth - that.padding.left - that.padding.right;
		that.svgH = that.innerHeight - that.padding.top - that.padding.bottom;
			
	
		that.svg;
		
	
		that.probNumTakes = {};
		that.probIdArr = [];
		that.maxNumTakers  = 0;
		
		//console.log("Constructor called");
		that.svg = d3.select("body").append("svg")
			  		 .attr("class", "gradechart")
			  		 .attr("width", that.outerWidth)
			  		 .attr("height", that.outerHeight)
					 .append("g")
					 .attr("transform", "translate(" + that.margin.left + "," + that.margin.top + ")");
		
		
		that.xScale = d3.scale.ordinal()
			// 0-->width, padding, and outer padding
			// (i.e. left and right margins): 
			.rangeRoundBands([that.barGap, that.svgW - that.barGap], .20, .5);
		
		that.yScale = d3.scale.linear()
			//.domain([0, 2]) // **** don't want that, want that set in commented below.
			.range([that.svgH, 0]); //*****?
		
		
	}();
	
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
		
		var gradeBars = that.svg.selectAll("rect")
		    	.data(gradeObjs, function(d) {
		    			// Return the tuple's problemId as
		    			// unique identifier:
		    			return d["probId"];
		    	 })
		    	 
		    	// Updates of existing bars:
		    	 
		    	.attr("x", function(d) {
		    		return that.xScale(d["probId"])
 		    	 })
				.attr("y", function(d) {
					var numTakers =  that.probNumTakes[d["probId"]];
		    		return that.yScale(numTakers);
		    	 })
		    	.attr("width", that.xScale.rangeBand())
		    	.attr("height", function(d) {
		    		return that.svgH - that.yScale(that.probNumTakes[d["probId"]]);
		    	 })
		    	
		    	// Done updating existing grade bars.
		    	// Now add bars for any new problems that
		    	// were delivered.
		    	.enter()
		    	// Add elements for the new data: 
		    	.append("rect")
				.attr("x", function(d) {
					probId = d["probId"];
					// Name this rectangle object by the probId
					// it represents:
					this.setAttribute("id", probId);
					this.setAttribute("class", "gradebar")
					return that.xScale(probId);
				})
				.attr("y", function(d) {
					// Another learner to incorporate into the chart.
					// How many attempts did his problem id take in 
					// total across all learner?
					var numTakers =  that.probNumTakes[d["probId"]];
					return that.yScale(numTakers);
				 })
				.attr("width", that.xScale.rangeBand())
				.attr("height", function(d) {
					var probId = d["probId"];
					var numTakers = that.probNumTakes[probId];
					return that.svgH - that.yScale(numTakers);
				 });
	}
	
	/************************** Private Methods ********************/
	
	/*-----------------------
	 * createAxes
	 *-------------*/
	
	this.createAxes = function(xScale, yScale) {
		
		that.xAxis = d3.svg.axis()
					   .scale(xScale)
					   .orient("bottom");
		that.svg.append("g")
			.attr("id", "xAxisGroup")
			.attr("class", "axis")
			//*****.attr("transform", "translate(0, " + that.svgH + ")")
			.call(that.xAxis);
		
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
			if (typeof that.probNumTakes[probId] === 'undefined') {
				// Got a problem ID we've never seen;
				// remember that this new problem had
				// nobody take it yet:
				that.probNumTakes[probId] = numAttempts;
				that.probIdArr.push(probId);
				haveNewProbId = true;
			} else {
				that.probNumTakes[probId] += numAttempts;
			}
			if (that.probNumTakes[probId] > that.maxNumTakers) {
				that.maxNumTakers = that.probNumTakes[probId];
			}
		}

		if (haveNewProbId) {
			that.xScale.domain(that.probIdArr);
			// Update the xAxis labels:
			that.xAxis.tickFormat(function(d) {
						return that.probIdArr.indexOf(d["probId"]);
						})
		}
		
		that.yScale.domain([0, that.maxNumTakers]);
		

	}
	
	this.createAxes(that.xScale, that.yScale);
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


