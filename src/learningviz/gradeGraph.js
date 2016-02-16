"use strict"
/*
 * TODO:
 *     o Add optional callback function to subscribeToTopic() 
 *     o put %correctness for each problem part into tooltip table.
 *     o add deselecting of gradebar by clicking anywhere
 *     o speed control?
 *     o in tooltip table: Part<n>: n needs to be 1-based

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
 *    partsCorrectness		  ++--+
 * 
 * Underlying query (It will have an extra '0' or '1' in
 * the first column; to avoid that, use only the second
 * SELECT, ordering just by firstSubmit, and manually adding
 * the column headers at the top of the resulting csv file.):
 *    
 *    SELECT *
 *    INTO OUTFILE '/tmp/cs145Grades.csv'
 *    FIELDS TERMINATED BY "," OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n'
 *    FROM
 *     (
 *        SELECT 0 AS sortKey, 'course','learner','percentGrade','attempts','firstSubmit', 'lastSubmit','probId','partsCorrectness'
 *        UNION ALL
 *        SELECT 1 AS sortKey,
 *            course_display_name AS course,
 *            anon_screen_name AS learner,
 *            percent_grade AS percentGrade,
 *            num_attempts AS attempts,
 *            first_submit AS firstSubmit,
 *            last_submit AS lastSubmit,
 *            module_id AS probId,
 *            parts_correctness AS partsCorrectness 
 *        FROM ActivityGrade
 *        WHERE course_display_name = 'Engineering/db/2014_1'
 *          AND num_attempts > -1
 *    ) AS MyData
 *    ORDER BY sortKey, lastSubmit;
 *
 * If the dates firstSubmit and lastSubmit are not valid dates, as 
 * recognized by JS's Date.parse() then the respective row is skipped.
 * 
 * The partsCorrectness is expected to be empty, or contain a series
 * of plus and minus characters. Each character stands for correctness
 * or incorrectness of one problem part in the assignment that the row
 * represents. See http://datastage.stanford.edu, search for ActivityGrade
 * table definition. If the partsCorrectness contains any characters 
 * other then plus/minus, the parts-correctness in the toolkit panel
 * for the respective problem will be omitted.
 *  
 * 
 * [Player button color: RGB=165,136,58 
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

/*-----------------------
 * deSelect
 *----------*/

/**
 * Add function moveToFront() to d3's 'selection()'
 * prototype. Use it to bring svg elements to the front.
 * Ex.:
 *     ...
 *  	.on("mouseover",function(){
 *  	        var sel = d3.select(this);
 *  	        sel.moveToFront();
 *  	      });
 */

d3.selection.prototype.moveToFront = function() {
  return this.each(function(){
  this.parentNode.appendChild(this);
  });
};

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
	my.outerWidth = 700,
	my.outerHeight = 500,
	//****my.margin = {top: 10, right: 10, bottom: 10, left: 10},
	my.margin = {top: 0, right: 0, bottom: 0, left: 0},
	//****my.padding = {top: 10, right: 10, bottom: 10, left: 10},
	my.padding = {top: 10, right: 0, bottom: 0, left: 10},
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
	my.transitionDuration = 500;      // milliseconds
	my.tooltipFadeoutDuration = 500;
	my.tooltipFadeinDuration = 750;
	
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
	
	// Total attempts by all learners on all assignments:
	my.totalAttempts = 0;
	
	// Sum of the success rates of all problems:
	my.sum1stSuccesses = 0;
	
	// Average rate of first success across
	// all problems. Success 'rate' of one 
	// problem is percentage of all takers
	// of that problem who succeeded on the
	// first try.
	my.mean1stSuccessRate = 0;

	my.selectedOutline = "red solid 2px";
		
	/************************** Initialization ********************/
	
	
	/*-----------------------
	 * init
	 *-------------*/
	my.init= function() {
		
		my.svg = d3.select("#chart").append("svg")
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
		
		// The tooltip area: just a hidden div, styled
		// via css:
		my.tooltip = d3.select("body").append("div")
			.attr("class", "tooltip")
			.attr("display", "inline")
			.attr("id", "tooltip")
			.style("visibility", "hidden");
		
		// Get a D3 drag behavior for use with the tooltip:
		var drag = d3.behavior.drag()
        			.on("drag", function() {
        				var tooltipRect = this.getBoundingClientRect();
        			    this.style.left = (tooltipRect.left + d3.event.dx)+'px';
        			    this.style.top  = (tooltipRect.top  + d3.event.dy)+'px';
        			});		

		// Make tooltip div draggable:
		my.tooltip.call(drag);		
		
		// Tooltip that appears when brushing over a
		// gradebar:
		my.brushTooltip = d3.select("body").append("div")
			.attr("class", "brushTooltip")
			.attr("id", "brushTooltip")
			.attr("display", "inline")
			.style("visibility", "hidden");
		
		// Bottom of the clock node (for placing the top of the tooltip panel):
		var clockRect = document.getElementById("clock").getBoundingClientRect();
		my.clockBottom = clockRect.top + clockRect.height;
		
		// Bar that is currently selected, i.e. 
		// someone clicked on it:
		my.selectedEl = null;
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
		try {
			var newProbGradeObjs = my.updateDataRepAndScales(gradeObjs);
		} catch(err) {
			console.log(err.message);
			return;
		}

		my.rescaleAxes();
		
		// Update height of existing bars, and add
		// new ones as needed:
		
		// Data is array of problem ids for *all*
		// problems seen so far, in time order:
		var gradeBarGroups = my.svg.selectAll(".gradebarGroup")
		    	 .data(my.probIdArr);

		// UPDATE existing rects: nothing special to do
		//        for them.

		// ENTER new bar groups for the never-seen problems:
		var enterSelection = gradeBarGroups
							    .enter()
							    .append("g")
							    .attr("class", "gradebarGroup");
		
		enterSelection.append("rect")
		    	    	 .attr("class", "gradebar")
		    	    	 .attr("id", function(probId) {
		    	   	 	 	return probId;
		    	    	 });     
        enterSelection.append("line")
		    	    	 .attr("class", "localMeanLine")
		    	    	 .attr("id", function(probId) {
		    	    	 	return probId + 'localMeanLine';
		    	    	 })   
		enterSelection.append("line")
		    	    	 .attr("class", "globalMeanLine")
		    	    	 .attr("id", function(probId) {
		    	    	 	return probId + 'globalMeanLine';
		    	    	 });
        
        // Add a brush-tooltip that appears while brushing
        // over a gradebar, and a mousedown for selecting
        // gradebars:
        
        // Add tooltip-showing when user clicks on a bar:
        enterSelection.on("mouseenter", function() {
        					my.brushIn(d3.event);
        				    })
        			  .on("mouseout", function() {
        				    my.brushOut(d3.event);
        				    })
        			  .on("mousedown", function() {
        				    my.selectEl(d3.event);
        			        })
		    	 
	    // Both new and old rects: update sizes
		// and locations on X-axis:
				    	// Place this rectangle object by the probId
				    	// it represents:
		 gradeBarGroups.select(".gradebar")
		 		  .attr("x", function(probId) {
		 			  	return my.xScale(probId);
						})
				  .attr("y", function(probId) {
						return my.yScale(my.probStats[probId].numAttempts);
					 	})
				  .each(function(probId) {
					  	var rect = this;
						// How many attempts did his problem id take in 
						// total across all learner?
						var numTakers   = my.probStats[probId].numAttempts;
						var num1stSuccesses = my.probStats[probId].num1stSuccesses;
						// How many 1st-time successes would this problem
						// have by the global average success rate?
						var num1stSuccessesByGlobal = numTakers * my.mean1stSuccessRate;
					  
		 			  	// Update the x coords of the local mean line:
		 			  	d3.select(this.parentNode).select(".localMeanLine")
		 			  		.attr('x1', rect.x.baseVal.value)
		 			  		.attr('x2', rect.x.baseVal.value + my.xScale.rangeBand())
							.attr("y1", my.yScale(num1stSuccesses))
							.attr("y2", my.yScale(num1stSuccesses));
		 			  	
		 			  	d3.select(this.parentNode).select(".globalMeanLine")
		 			  		.attr('x1', rect.x.baseVal.value)
		 			  		.attr('x2', rect.x.baseVal.value + my.xScale.rangeBand())
							.attr("y1", my.yScale(num1stSuccessesByGlobal))
							.attr("y2", my.yScale(num1stSuccessesByGlobal));
				  })	
				  // Selection is still a rect: 
				  .attr("width", my.xScale.rangeBand())
				  .attr("height", function(probId) {
						var numTakers = my.probStats[probId].numAttempts;
						return my.chartHeight - my.yScale(numTakers);
					 	})
				  .transition().duration(my.transitionDuration)
				  .style("opacity", 1);

		 // Update clock: time/date of last data object:
		 document.getElementById("clock").innerHTML = gradeObjs[gradeObjs.length -1 ].lastSubmit
	}
	
	/************************** Private Methods ********************/

	/*-----------------------
	 * selectEl
	 *----------*/
	
	/**
	 * Given a mouse-down event. If mouse is over a gradear select it.
	 * If another gradebar is currently selected, de-select that.
	 * If mouse-down was over anything other than a gradebar, just
	 * de-select my.selectedEl and set my.selectedEl to null
	 * 
	 * :param event: the mouse-down event over one gradebar
	 * :type event: Event
	 */

	my.selectEl = function(event) {
		var mouseX = event.pageX;
		var mouseY = event.pageY;
		event.stopPropagation();
		
		// Mouse may have been clicked on the local- or global
		// mean lines that lie on top of gradebars. For those
		// cases, find the underlying gradebar. If mouse was
		// clicked on the gradear directly, no harm done. If
		// clicked outside of gradebar, null is returned:
		
		var eventEl = my.siblingGradeBar(event.target);

		
		// Clicking anywhere outside either a gradebar
		// deselects and removes any possibly selected
		// gradebar selection and the toolbar panel.
		// Note that the toolbar panel catches mouse events
		// on top if *it*:
		if (eventEl == null) {
			// Clicked outside of any grade bar;
			// If one is selected, de-select it now:
			my.deSelectEl(my.selectedEl);
			return;
		}
		if (eventEl !== my.selectedEl) {
			// User mouse-downed on a grade bar, but
			// another bar is already selected; de-select
			// that first; if nothing is selected,
			// my.selectedEl will be null, which is fine:
			my.deSelectEl(my.selectedEl);
		}
		// New gradebar is selected; remember it:
		my.selectedEl = eventEl;
		// Put a border around the bar:
		eventEl.style.outline = my.selectedOutline;
		
		my.prepareTooltip(eventEl);
		my.tooltip.transition().duration(my.tooltipFadeinDuration)
							   .style('opacity', 1)
							   .each("start", function() {
								        my.tooltip.style('opacity', 0);
  								        my.tooltip.style('visibility', 'visible');
							   });
	}

	/*-----------------------
	 * prepareTooltip
	 *----------*/
	
	/**
	 * Fills the tooltip panel with the information of the selected gradebar.
	 * defines dimensions and position of the tooltip panel, but does not
	 * make the panel visible.
	 * 
	 * :param gradebar: the gradebar that was clicked to pull up the tooltip
	 * :type gradebar: rect
	 */
	
	my.prepareTooltip = function(gradebar) {
		var populateTooltip;
		var probId = gradebar.id
		var totalNumAttempts = my.probStats[probId].numAttempts;
		var firstSuccesses = my.probStats[probId].num1stSuccesses;
		var firstSuccessRate = my.probStats[probId].successRate;
		var partsStats = my.probStats[probId].partsCorrectness;
		var partsTriesDistrib = my.probStats[probId].partsTriesDistrib;
		var numParts = 'unknown';
		if (typeof partsStats !== 'undefined') {
			numParts = partsStats.length;
		}
		
		// This version puts it to the upper right of the chart area:
		my.tooltip
			.each(function() {
				this.innerHTML = 
				`<span style="padding-right 100px">Problem:</span> ${probId}<br>
				 Total number of attempts: ${totalNumAttempts}<br>
				 First-try-success: ${firstSuccessRate == 100 ? 100 : firstSuccessRate.toPrecision(2)}%<br>
				 Global first-try-success: ${100 * my.mean1stSuccessRate.toPrecision(2)}%<br> 
				 Number of parts: ${numParts}<br>`;
				 if (typeof partsStats !== 'undefined') {
					this.innerHTML += `For each problem part: percent of correct solutions
					                   and median required attempts:
					                   ${my.prepareTooltipGradeStatsTable(partsStats, totalNumAttempts, partsTriesDistrib)}
					                  `;
				}
			})
			.style("width", function() {
				return this.clientWidth + 1;
			})
			// Put left edge of tooltip such that the tooltip panel
			// ends just within the chart area:
			.style("left", (my.chartOriginX + my.outerWidth - my.tooltip.node().clientWidth) + "px")
			// Place top of tooltip panel just below the clock:
			.style("top",  + my.clockBottom + "px")
	}
	
	/*-----------------------
	 * prep1ProbGradeStatsTable
	 *----------*/
	
	/**
	 * Prepares the HTML grades table that's part of a gradebar's tooltip.
	 * Tooltips show details about one problem. One such detail is the table.
	 * 
	 * The table format is:
	 *                                     Part1       Part2       Part3
	 *  Percent completions                89%          3%         100%
	 *  Median required tries               1            4           2
	 *  
	 * :param partsStats: array with each element containing the total number of
	 *                    learners who have completed for one part of the problem.
	 *                    The number is regardless of the number of tries: Eventually completed.
	 * :type partsStats: [int]
	 * :param numAttempts: total number of attempts on the problem, regardless of part and success.
	 * :type numAttempts: int
	 * :param attemptTriesDistrib: a Map with one key/value pair for each problem part. 
	 *                             The key is the index of the problem part: part1 is 1, etc.
	 *                             Values are arrays. Each element at index I of such an array holds
	 *                             an integer, which is the count of learners who took I tries
	 *                             to complete the Part-I of the problem.
	 * :type attemptTriesDistrib: Map(int -> int)
	 * :returns: HTML string that will display as the table.
	 * :rtype: str   
	 */
	
	my.prepareTooltipGradeStatsTable = function(partsStats, numAttempts, partsTriesDistrib) {
		// Cause horizontal scrollbar if needed (overflow-x:auto). 
		// Also add an initial column <th></th> to the header of the
		// table to allow for the the explanatory left-most column:
		var tableHtml = `<div class="probCorrectTblDiv" style="overflow-x:auto;"> 
						   <table class="probCorrectTbl"> 
		                     <tr> 
		                       <th></th>`;

		// Add html for the table header:
		for (var i=0; i<partsStats.length; i++) {
			tableHtml += `<th>Part${i}</th>`
		}
		// Close the header row:
		tableHtml += `</tr>
		                <tr>
		                  <td>Percent completions (incl. >1 try)</td>`
		// Add 1st-success percentages for each problem part:		                
		for (var i=0; i<partsStats.length; i++) {
			// Round to nearest percent before multiplying by 100:
			var percentageCorrect = 100 * (partsStats[i]/numAttempts).toPrecision(2);
			tableHtml += `<td>${percentageCorrect}%</td>`
		}
		tableHtml += `</tr>
		                <tr>
		                  <td>Median required tries</td>`;
		// Add median of number of required tries for each part;
        // The partsTriesDistrib is an array whose index corresponds
        // to a number of tries, and the corresponding value is 
		// how often that number of tries was required. Since
		// zero tries is meaningless, the first element is always
		// undefined; therefore the slice:
        for (var distribArray of partsTriesDistrib.values()) {
        	var median = my.median(distribArray.slice(1));
        	// If nobody has gotten a part correct, median will be undefined:
        	if (isNaN(median)) {
        		median = "n/a";
        	}
        	tableHtml += `<td>${median}</td>\n`
        }
        tableHtml += `</tr></table></div>`;

        return tableHtml;
	}
	
	
	/*-----------------------
	 * deSelectEl
	 *----------*/
	
	/**
	 * Given a visual object, indicate that it is not selected.
	 * We remove the outline, and set my.selectedEl to null.
	 * We hide the tooltip. It is OK to pass in null. The 
	 * function will simply return.
	 */
	
	my.deSelectEl = function(el) {
		if (el === null) {
			return;
		}
		el.style.outlineStyle = "";
		my.tooltip.style('visibility', 'hidden');
		my.selectedEl = null;
	}

	/*-----------------------
	 * brushIn
	 *--------------*/
	
	/**
	 * User brushed into one of the gradebars.
	 * Make brush-tooltip visible. 
	 */
	
	my.brushIn = function(event) {
		var mouseX = event.pageX;
		var mouseY = event.pageY;
		var tooltipHeight = my.brushTooltip.style.minHeight;
		my.brushTooltip.text("Click on bar for details.");
		my.brushTooltip
			.style("left", (mouseX - 34) + "px")
			//.style("top", (mouseY - 12) + "px")
			.style("top", (mouseY - 60) + "px")
			.style('visibility', 'visible');
		
		my.brushTooltip.style('visibility', 'visible');
	}
	
	/*-----------------------
	 * brushOut
	 *--------------*/
	
	/**
	 * User brushed out of a gradebar.
	 * Make brush-tooltip invisible. 
	 */
	
	my.brushOut = function(event) {
		my.brushTooltip.style('visibility', 'hidden');
	}
	
	/*-----------------------
	 * gradeBarMoved
	 *----------*/
	
	/**
	 * Called with event when a gradebar moves along the x axis.
	 * This occurs when the x axis is rescaled. We take two
	 * actions: if a brushTooltip is visible, we fade it out.
	 * If a full tooltip is visible, we update its callout line
	 * to the selected bar.
	 */
	
	 my.gradeBarMoved = function(event) {
		 if (my.brushTooltip.style('visibility') === 'visible') {
			 my.brushTooltip
				  .transition().duration(my.tooltipFadeoutDuration)
				  // Fade out, and get callback at the end to 
				  // set the brushTooltip's visibility to 'hidden':
				  .style("opacity", 0).each("end", function() {
					  my.brushTooltip.style('visibility', 'hidden');
					  my.brushTooltip.style('opacity', 1);
				  })
		 }
	 }
	
	/*-----------------------
	 * updateDataRepAndScales
	 *-------------*/

	my.updateDataRepAndScales = function(gradeObjs) {
		/**
		 * Given incoming array of grade objects, go through
		 * each object and update our records of how many
		 * attempts that problem received so far, as well
		 * as its success rate and number of successes on 
		 * first attempt.
		 *  
		 * Globally across all problems we also
		 * update the maximum number of attempts that any problem
		 * received, the array of all problem ids (if a problem
		 * hasn't been seen before), and the mean success rate
		 * across all problems.
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
		 * :param gradeObjs: is a an array of objs that contain all 
		 *         information associated with a grade, such as learner ID,
		 *         course, number of attempts, grade, etc.:
		 * :type gradeObjs: [{}]
		 * :return: array of gradeObj for problems for which we haven't had
		 *      information delivered before.
		 * :rType: [{}]
		 */
		
		var newProblemObjs = [];
		
		for (var i=0, len=gradeObjs.length; i<len; i++) {
			var gradeObj = gradeObjs[i];
			var probId = gradeObj["probId"];
			if (typeof probId === "undefined") {
				console.log("New data has no 'probId' field: " + JSON.stringify(gradeObj, null, 4));
				continue;
			}
			var newNumAttempts = parseInt(gradeObj["attempts"]);
			if (isNaN(parseInt(newNumAttempts)) || 
				newNumAttempts < 1) {
				console.log("New data has no, or negative 'attempts' field: " + JSON.stringify(gradeObj, null, 4));
				continue;
			}
			var percentGrade = parseFloat(gradeObj["percentGrade"]);
			if (isNaN(parseFloat(percentGrade)) || 
				percentGrade < 0) {
				console.log("New data has no, or negative 'percentGrade' field: " + JSON.stringify(gradeObj, null, 4));
				continue;
			}
			
			var firstSubmit = new Date(Date.parse(gradeObj['firstSubmit']));
			if (!my.isValidDate(firstSubmit)) {
				console.log("New data has bad firstSubmit field: " + JSON.stringify(gradeObj, null, 4));
				continue;
			}
			
			var lastSubmit = new Date(Date.parse(gradeObj['lastSubmit']));
			if (!my.isValidDate(lastSubmit)) {
				console.log("New data has bad lastSubmit field: " + JSON.stringify(gradeObj, null, 4));
				continue;
			}
			
			// The parts-correctness column is optional. If present,
			// it will contain plus- and minus characters, one for each
			// part of the problem:
			var partsCorrectness = gradeObj['partsCorrectness']
			if (typeof partsCorrectness === 'undefined') {
				partsCorrectness = null;
			}
			
			// Tmp to remember old number of a prob's
			// attempts after updating that number:
			var prevNumAttempts = 0;
			
			if (typeof my.probStats[probId] === 'undefined') {
				// Got a problem ID we've never seen;
				// remember that this new problem had
				// nobody take it yet:
				my.probStats[probId] = {}
				my.probStats[probId].numAttempts = newNumAttempts;
				// How often this problem was successfully taken
				// with one try:
				my.probStats[probId].num1stSuccesses = 0;
				my.probStats[probId].successRate = 0;
				my.probStats[probId].earliestSubmit = firstSubmit;
				my.probStats[probId].mostRecentSubmit = lastSubmit;
				// Is problem-parts results available?:
				if (partsCorrectness !== null) {
					// Make array the length of the number of parts
					// this assignment has; we'll use it to keep
					// count of how many learners have each part correct
					// so far (regardless of how many tries they took:
					my.probStats[probId].partsCorrectness = new Array(partsCorrectness.length).fill(0);
					// Create data structure for keeping arrays of number of
					// attempts it took to get each part correct (for median computation);
					// Think histogram of attempts taken till success:
					// {1 : [3,4,10],                  <-- 3 took 1 try, 4 took 2 tries, 10 took 3 tries
					//  2 : [5,4,undefined,10,1,1,3]   <-- undefined: nobody took 3 tries.
					// }
					my.probStats[probId].partsTriesDistrib = new Map();
					for (var i=0; i<partsCorrectness.length; i++) {
						// Make the distrib Map keys correspond to the
						// 1-based problem part number; therefore i+1:
						my.probStats[probId].partsTriesDistrib.set(i+1, [])
					}
				}
				my.probIdArr.push(probId);
				// Remember the info about this new problem:
				newProblemObjs.push(gradeObj);
				var haveNewProbId = true;
			} else {
				prevNumAttempts = my.probStats[probId].numAttempts;
				my.probStats[probId].numAttempts += newNumAttempts;
				// Update earliest/latest submit dates for this
				// existing problem:
				if (firstSubmit < my.probStats[probId].earliestSubmit) {
					my.probStats[probId].earliestSubmit = firstSubmit;
				}
				if (lastSubmit > my.probStats[probId].mostRecentSubmit) {
					my.probStats[probId].mostRecentSubmit = lastSubmit;
				}
			}
			
			// Update the problem's record of how often each problem part
			// was gotten right so far, and account of how many tries
			// were needed for each part (for median computation):
			if (partsCorrectness !== null) {
				for (var i=0; i<partsCorrectness.length; i++) {
					if (partsCorrectness === '+') {

						// One more learner got part i correct (no matter how many tries):
						my.probStats[probId].partsCorrectness[i] += 1;

						// For each problem part, update array whose positions track
						// attempts: Pth position holds number of learners who got that problem
						// part correct on Pth try; i.e. partsTriesDistrib is 1-based:
						var probPartAttemptsHistory = my.probStats[probId].partsTriesDistrib.get(i+1)
						// Has anyone before taken exactly this learner's number of attempts
						// to get the part correct?
						if (Number.isInteger(probPartAttemptsHistory[newNumAttempts])) {
							// Yes. 
							probPartAttemptsHistory[newNumAttempts] += 1;
						} else {
							// Nobody took this exact numbers of tries before; if assignment
							// leaves holes, they will be set to undefined:
							probPartAttemptsHistory[newNumAttempts] = 1;
						}
					}
				}				
			}
			
			
			// Update largest number of takers among all problems
			// (i.e. the highest Y-value:
			if (my.probStats[probId].numAttempts > my.maxNumTakers) {
				my.maxNumTakers = my.probStats[probId].numAttempts;
			}
			// More attempts at problems; update the total
			// number of attempts:
			my.totalAttempts += newNumAttempts;

			// For this problem: update the number of
			// learners who got the problem on the first try.
			// This also means updating the overall 1st-try-success
			// average across all problems:
			if (newNumAttempts == 1 && percentGrade == 100.0) {
				my.probStats[probId].num1stSuccesses += 1;
				var successes = my.probStats[probId].num1stSuccesses; 
				my.probStats[probId].successRate = 
					100 * successes/my.probStats[probId].numAttempts;
				// Update sum of all problems' successes:
				my.sum1stSuccesses += 1;
				
				// Update the rate of 1st-time success across all problems:
				my.mean1stSuccessRate = my.sum1stSuccesses/my.totalAttempts;
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

			// Uncomment to get X-axis ticks (1,2,3,...)
			// But looks ugly when many bars are present:
/*			my.xAxis.tickFormat(function(d) {
						return my.probIdArr.indexOf(d) + 1;
						})
*/
			my.xAxis.tickFormat(function(d) {
						return '';
						})
			my.xAxis.ticks([]);
			
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
				// Call my.gradebarMoved() to make corrections
				// to any widgets that refer to the gradebars,
				// because if the x-axis title moved, then they
				// moved as well:
				.each("end", my.gradeBarMoved)
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
					   .orient("bottom")
					   .ticks(0); // Remove if you want tick lines.
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
	
	/*-----------------------
	 * isValidDate
	 *----------*/
	
	/**
	 * Given an item, return true if the item is a valid
	 * date object. Else return false.
	 * 
	 * :param maybeDate: the element to test.
	 * :type maybeDate: <any>
	 * :return true if maybeDate is a valide Date object, else false.
	 * :rtype: bool
	 */
	
	my.isValidDate = function(d) {
	  if ( Object.prototype.toString.call(d) !== "[object Date]" )
	    return false;
	  return !isNaN(d.getTime());
	}

	/*-----------------------
	 * median
	 *----------*/
	
	my.median = function(values) {
	
	    values.sort( function(a,b) {return a - b;} );
	    var half = Math.floor(values.length/2);
	    if(values.length % 2) {
	        return values[half];
	    }
	    else {
	        return (values[half-1] + values[half]) / 2.0;
	    }
	}	
	
	/*-----------------------
	 * pointInRect
	 *----------*/
	
	/**
	 * Given x/y, and a ClientRect object, return true if
	 * point is within the rectangle.
	 * 
	 * :param pointX: x-coordinate of point
	 * :type pointX: float
	 * :param pointY: y-coordinate of point
	 * :type pointY: float
	 * :param rect: the client rectangle as returned by Element.getBoundingClientRect() 
	 * :type rect: ClientRect
	 */
	
	my.pointInRect = function(pointX, pointY, rect) {
		if (pointX >= rect.left &&
			pointX <= rect.right &&
			pointY >= rect.top &&
			pointY <= rect.bottom
		) {
			return true;
		} else {
			return false;
		}
	}
	
	
	/*-----------------------
	 * siblingGradeBar
	 *----------*/
	
	/**
	 * Given an element, return its sibling that is a gradebar,
	 * if one exists, else return null.
	 * 
	 * :param element: the element whose gradebar-sibling to search for
	 * :type element: <any>
	 * :return the gradebar node, or null.
	 */
	
	my.siblingGradeBar = function(element) {
		try {
			return (element.closest(".gradebarGroup")).querySelector('.gradebar');
		} catch (typeError) {
			var result = null;
		}
		return result;
	}
	
	/************************** Top-Level Statements ********************/
	
	// Make click anywhere de-select gradebar if one is
	// currently selected. Done in 'selectEl():
	window.addEventListener('mousedown', function(event) {
		if (!my.pointInRect(event.pageX, event.pageY, my.tooltip.node().getBoundingClientRect()) &&
 			my.selectedEl !== null) {
			my.selectEl(event);
		}
	});
	
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
