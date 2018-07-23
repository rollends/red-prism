function [A,U,P] = clusterTransform(file, groupCount)
    load(file, 'A');
    row_sums = sum(A, 2);
    U = find(row_sums);

    D_inv = spdiags(1 ./ row_sums(U), 0, size(A(U,U), 1), size(A(U,U), 2));

    S = A(U,U);
    L_rwhat = D_inv*S;

    % Saving Memory
    clear D_inv;
    clear row_sums;
    
    [V, l] = eigs(L_rwhat, groupCount, 1.01);
    l = diag(l);
    
    % Sort by real component.
    [~, I] = sort(l);
    l = l(I);
    V = V(:,I);
    
    I = (real(l)<=1) & (abs(l)>=0);
    V_p = V(:,I);
    K = size(V_p, 2);
    
    % Saving Memory
    clear I;
    clear V;
    clear l;
    
    % K-means
    cluster_index = kmeans([real(V_p), imag(V_p)], K);
    
    % Saving Memory
    clear V_p;

    % Sort the resulting choices so that they group up.
    [~, G] = sort(cluster_index);
    
    % Saving Memory
    clear cluster_index;

    % Constructing resulting transformation matrix with identification
    % matrix.
    P = sparse(1:size(S,1), G, ones(size(S,1),1));
end