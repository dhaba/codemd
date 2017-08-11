def extract_interval_params(request_args):
    """
    Take a url request object and extracts the associated intervals and returns
    them as a list of tuples

    params request_args: an instance of request.args
    return: A list of lists, ie [[start1, end1], [start2, end2]]
    """
    intervals = [[None, None], [None, None]]
    start1, end1 = request_args.get("start1"), request_args.get("end1")
    start2, end2 = request_args.get("start2"), request_args.get("end2")
    if ((start1 and end1) and (start1 != 'null') and (end1 != 'null')):
        intervals[0] = [int(start1), int(end1)]
    if ((start2 and end2) and (start2 != 'null') and (end2 != 'null')):
        intervals[1] = [int(start2), int(end2)]

    return intervals
