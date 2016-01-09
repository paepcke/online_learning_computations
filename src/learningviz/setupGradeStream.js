// TODO:
//   o If num_attempts missing, assume 1.

//console.log(vizzer);
var gradeReceiver = function(gradeData) {
	console.log(gradeData);
	vizzer.updateViz([gradeData]);
}

var bus;
var promise = busInteractor.getInstance();
promise.then(function(instance) {
	bus = instance;
	kickoff();
    },
	function(err_msg) {
		alert(err_msg);
	}
);

var kickoff = function() {
	bus.setMsgCallback(gradeReceiver);
	bus.subscribeToTopic('gradesCompilers');
	//*****
	//bus.subscribedTo(function(subscriptions) { console.log (subscriptions)});
	//*****
	
}									  
									  


var testData = 
			nextData = [
					   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
					    "learner" : "6a6c70f0f9672ca4a3e16bdb5407af51cd18e4e5",
					    "grade" : 10,
					    "attempts" : 3,
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


