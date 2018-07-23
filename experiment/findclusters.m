%% Analyzing /r/uwaterloo
file = 'data/groupdetector-uwaterloo.mat'

[A, U, P] = clusterTransform(file, 500);

f = figure(1);

ax = subplot(1, 2, 1);
spy(A(U,U),1)
title(ax, 'Original Adjacency Matrix');

ax = subplot(1, 2, 2)
spy(P*A(U,U)*P',1)
title(ax, 'Permuted Adjacency Matrix');

f.PaperType =  '<custom>';
f.PaperPosition = [0 0 6 3];
f.PaperUnits = 'inches';
f.PaperSize = [6 3];
print(f, 'fig/uwaterloo.eps', '-deps', '-r300');
save('data/uwaterloo-cluster');
clear all;

%% Analyzing /r/science
file = 'data/groupdetector-science.mat'

[A, U, P] = clusterTransform(file, 500);

f = figure(1);

ax = subplot(1, 2, 1);
spy(A(U,U),1)
title(ax, 'Original Adjacency Matrix');

ax = subplot(1, 2, 2)
spy(P*A(U,U)*P',1)
title(ax, 'Permuted Adjacency Matrix');

f.PaperType =  '<custom>';
f.PaperPosition = [0 0 6 3];
f.PaperUnits = 'inches';
f.PaperSize = [6 3];
print(f, 'fig/science.eps', '-deps', '-r300');
save('data/science-cluster');
clear all;

%% Analyzing /r/CanadianInvestor
file = 'data/groupdetector-CanadianInvestor.mat'

[A, U, P] = clusterTransform(file, 500);

f = figure(1);

ax = subplot(1, 2, 1);
spy(A(U,U),1)
title(ax, 'Original Adjacency Matrix');

ax = subplot(1, 2, 2)
spy(P*A(U,U)*P',1)
title(ax, 'Permuted Adjacency Matrix');

f.PaperType =  '<custom>';
f.PaperPosition = [0 0 6 3];
f.PaperUnits = 'inches';
f.PaperSize = [6 3];
print(f, 'fig/CanadianInvestor.eps', '-deps','-r300');
save('data/CanadianInvestor-cluster' );
clear all;