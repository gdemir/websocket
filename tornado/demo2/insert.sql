use CHAT;

# Users
	insert into Users (username, password, state_id)
	values('gdemir1', '159654', 0);
	insert into Users (username, password, state_id)
	values('gdemir2', '159654', 0);
	insert into Users (username, password, state_id)
	values('gdemir3', '159654', 0);

# Messsages

	insert into Messages (sender_user_id, recipient_user_id, body)
	values(1, 2, 'bu bir testtir');
	insert into Messages (sender_user_id, recipient_user_id, body)
	values(2, 1, 'bu ikinci bir testtir');
