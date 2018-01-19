# Overview

Code.MD is a web-based tool for interactively visualizing software using version control data. Our version control systems contain a rich database of social information, detailing every change to the codebase, as well as each unique developer responsible for those changes. By mining potentially millions of commits and file modifications, Code.MD is able to provide developers and managers with data driven insights to allow them to make highly informed design decisions, and diagnose problematic areas in their codebase before they become too unwieldy to fix.

The visualizations are built using a mixture of D3 and Crossfilter, run on a Flask framework and served using AWS.

Currently the site is offline pending issues with AWS, but will be back online shortly and a link will be included in this document.

Below is a summary of the features Code.MD has to offer. Click on the images to watch a short video showcasing each feature.

## Interactive Dashboard

[![IMAGE ALT TEXT](http://img.youtube.com/vi/OJ0czxnvvAQ/0.jpg)](http://www.youtube.com/watch?v=OJ0czxnvvAQ "Top Contributors")

The interactive dashboard provides developers and project managers with a means of quickly exploring the evolutionary history of their project. This can be used to help with release planning, pin-pointing patterns that cause an increase in bugs, and identifying the most prolific developers.

Users can interactively select an interval of commits between two dates, and visualize data pertinent to those selected commits, including:
	• Top Contributors
	• Bug Frequency
	• Code Churn

### Top Contributors

[![IMAGE ALT TEXT](http://img.youtube.com/vi/OJ0czxnvvAQ/0.jpg)](http://www.youtube.com/watch?v=OJ0czxnvvAQ "Top Contributors")

Top contributors allows users to understand which developers are writing the most code in a given time period. This metric can be particularly useful in open source projects where there are usually a select few developers contributing a majority of the code, and many other developers contributing small pieces.

### Bug Frequency

[![IMAGE ALT TEXT](http://img.youtube.com/vi/LOMac9hMVRQ/0.jpg)](http://www.youtube.com/watch?v=LOMac9hMVRQ "Bug Frequency")

Bug frequency shows developers how many bugs were present in across a project's lifecycle. Coupled with other metrics, bug frequency can be very useful to get an overview of the social factors that may induce bugs. Is there a sharp increase in bugs after a particular sprint or deadline? Is there a decrease in bugs after a large refactoring? Visualizing the distribution of bugs can help answer questions like these.

### Code Churn

[![IMAGE ALT TEXT](http://img.youtube.com/vi/_MWYrwxpGLc/0.jpg)](http://www.youtube.com/watch?v=_MWYrwxpGLc "Code Churn")

Tackling technical debt and refactoring can often play a large part in how many bugs turn up in future releases. Visualizing the total insertions and deletions to a code base, as well as the fluctuations in total lines of code can help developers access the effects of refactors, as well as the effects of new features.

## Circle Packing

[![IMAGE ALT TEXT](http://img.youtube.com/vi/yM-rzkDHHFY/0.jpg)](http://www.youtube.com/watch?v=yM-rzkDHHFY "Knowledge Map")

Once users have selected an interval of commits that they are interested in, they can generate a code packing visualization to get a closer look at file-specific data. Circle packing works by analyzing the file hierarchy of the project, and drawing a circle of each module in the project. Nested circle represent subcomponents of modules, and the size of the circles correspond to the total number of lines of code in each module. Finally, the innermost circles represent the actual objects in the system, which users can then mouse-over to view various file statistics.

# Knowledge Map

[![IMAGE ALT TEXT](http://img.youtube.com/vi/yM-rzkDHHFY/0.jpg)](http://www.youtube.com/watch?v=yM-rzkDHHFY "Knowledge Map")

Coordination is vital to the success of a large-scale software project. Knowledge map sheds light onto the distribution of knowledge throughout the system by identifying the top 3 developers who wrote the most code for each file.

This information can be used by developers and managers to determine who is most knowledgeable in some particular module, or alternatively to quantify the loss of information when a particular developer leaves the team.

Each color represents a unique developer, except for white which is used to represent all other developers when there are more developers than distinct colors.

The metrics are scoped to the selected temporal interval (which can be seen in the top right of the page). A "change" is defined as a single insertion or deletion to the file.

# Bug Score

[![IMAGE ALT TEXT](http://img.youtube.com/vi/F_9r3Ylyapo/0.jpg)](http://www.youtube.com/watch?v=F_9r3Ylyapo "Bug Score")

Bug score helps developers understand which files are causing the most bugs and are deserving of particular care. It works by counts the number of bugs associated with each file, and then using a sigmoid function that weighs recent bugs higher than older bugs to highlight the most problematic areas. These "hotspots" are colored in red, where darker shades indicate more severity.

The intuition that drives this algorithm is simple: if a file keeps requiring bug fixes, it is likely a problematic area worthy of special attention because developers are clearly struggling with it. The intention here is not to provide some kind of objective function for bug prediction, but rather to provide developers with data driven insights that can compliment their own intuitions. To facilitate exploration of different trends specific to different periods in a project's lifecycle, the computation of this algorithm is scoped to the selected temporal interval (which can be seen in the top right of the page).

The algorithm uses the scoring function
![Bug Score Equation](https://i.imgur.com/07AjftA.png)
where n is the number of bug-fixing revisions, and t_i is the timestamp of the i-th fix. The timestamps are normalized such that t_i is bounded within [0,1], where 0 represents the start of the selected interval, and 1 represents the end.

# Temporal Coupling

Temporal coupling helps developers spot bad architecture by measuring the tendency of files to change together. This can greatly assist in spotting unintentional dependencies between files, helping developers to diagnose problems early before they become too unwieldy and too expensive to fix.

The different colors here represent different cliques of coupled files, where a graph is drawn using the files as vertices and mutual changes as edges. The intensity of the color is proportional to the temporal coupling score.

Under the reasonable assumption that one particular revision implements a single feature or functionality, it should be relatively innocuous for files belonging to the same module to change together. This is because files belonging to the same module should implement complementary functionalities. However, files which belong to separate modules should seldom change together because they likely implement very different functionalities.

If files belonging to separate modules frequently change together, this can be indicative of deteriorating architecture because those files are possibly being required to take on new responsibilities that they were not originally intended to support.

Temporal coupling quantifies these potentially bad architectural patterns, by computing information including:
	• Number of Revisions: the number of revisions (a.k.a. commits) that modified the file in the temporal interval
	• Coupled File: The other file which most frequently appears in the same revision
	• Number of Mutual Revisions: The number of revisions that modified both the file and coupled file in the temporal interval
	• Percent Coupled: The percent of the file's revisions which also changed it's coupled counterpart (i.e. # of mutual revisions / # of revisions)

And finally the Temporal Coupling Score, which weights the percent coupled by the logarithm of sum of the number of revisions between the file and its coupled counterpart. This weight helps weed out files that have few too revisions to be of interest. The exact scoring function f(a, b) for the temporal coupling between files a and b is:
![Temporal Coupling Equation](https://i.imgur.com/SuJthHI.png)
where A and B are the sets of all commits changing files a and b respectively.
