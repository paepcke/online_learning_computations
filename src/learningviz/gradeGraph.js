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

var GradeInfoIndx = {
		COURSE : 0,
		LEARNER : 1,
		GRADE : 2,
		ATTEMPTS : 3,
		FIRST_SUBMIT : 4,
		LAST_SUBMIT : 5,
		PROBLEM_ID : 6
}

var testTuples = [
				   ["Medicine/HRP258/Statistics_in_Medicine",
				    "3e43611e9969f85c5354894e66822434a7ee61d8",
				    5,
				    2,
				    "2013-06-11 15:15:08",
				    "2013-07-16 06:43:23",
				    "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
				    ],
				    [
				     "Medicine/HRP258/Statistics_in_Medicine",
				     "6a6c70f0f9672ca4a3e16bdb5407af51cd18e4e5",
				     10,
				     1,
				     "2013-06-11 15:12:13",
				     "2013-07-07 00:10:51",
				     "i4x://Medicine/HRP258/problem/5542da143b054d0ba3efdb243b5eb343"
				     ],
				    ["Medicine/HRP258/Statistics_in_Medicine",
				     "cb2bb63c14e6f5fc8d21b5f43c8fe412c7c64c39",
				     7,
				     1,
				     "2013-06-11 15:21:11",
				     "2013-07-1506:13:51",
				     "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
					 ]
                  ];

function GradeCharter() {
	
	var that = this;
	
	that.svgW = 900;
	that.svgH = 100;
	//that.barW = 20;
	that.barGap = 4;
	that.vertScale = 5;

	that.svg;
	var xAxis;
	var yAxis;
	var xScale;
	var yScale;
	var xAxisPaddingHor;
	var xAxisPaddingVer;
	var yAxisPaddingHor;
	var yAxisPaddingVer;

	// Init the int --> ugly-problem-ID dict:
	//that.intToProbId = {};
	//****that.probIdToInt = {};
	
	that.probIdArr = [];
	that.maxGrade  = 0;
	
	// Number of distinct problem IDs encountered so far:
	//***********
	//that.num_probs = 0;
	that.numProbs = 3;
	//***********
	
	//console.log("Constructor called");
	that.svg = d3.select("body").append("svg")
		  		 .attr("width", that.svgW)
		  		 .attr("height", that.svgH);
	
	that.xscale = d3.scale.ordinal()
		.domain(that.probIdArr)
		// 0-->width, padding, and outer padding
		// (i.e. left and right margins): 
		.rangeRoundBands([0, that.svgW, .1, .3]);
	
	that.yscale = d3.scale.linear();
	
	GradeCharter.prototype.updateViz = function(tuples) {
		/*
		 * Public method called when a new set of grade info 
		 * tuples arrives.
		 */
		
		// Any problem ids we haven't seen yet?
		var haveNewProbId = false;
		for (var i=0, len=tuples.length; i<len; i++) {
			var tuple = tuples[i];
			var probId = tuple[GradeInfoIndx.PROBLEM_ID];
			var newGrade  = tuple[GradeInfoIndx.GRADE];
			if (that.maxGrade < newGrade) {
				that.maxGrade = newGrade;
			}
/*	****		if (typeof that.probIdToInt[probId] === 'undefined') {
				// New problem
				that.probIdArr.append(probId);
				haveNewProbId = true;
			}
*/		}
		
		that.yscale.domain([0,that.maxGrade]);
		
		// Scales will include all tuples: past and
		// this set, even if not all bars are visible in the
		// viewport:
		
		var rects = that.svg.selectAll("rect")
		    .data(tuples)
		    .enter()
		    .append("rect")
		    .attr("y", function(d) {
		    	// The subtraction makes bars grow bottom to top on screen:
		    	return that.svgH - that.yscale(d[that.GradeInfoIndx.GRADE]);
		     })
		    .attr("width", x.rangeBand())
		    .attr("height", function(d) {
		    	return that.svgH - that.yscale(d[GradeInfoIndx.GRADE])
		     })
			.attr("fill", "teal");
	}
}

vizzer = new GradeCharter();

console.log("I was loaded.");
vizzer.updateViz(testTuples);