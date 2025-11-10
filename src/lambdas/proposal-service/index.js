const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

const PROPOSALS_TABLE = process.env.PROPOSALS_TABLE;

exports.handler = async (event) => {
    console.log('Proposal service event:', JSON.stringify(event, null, 2));
    
    const headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    };

    try {
        const { httpMethod, pathParameters, body, queryStringParameters } = event;
        
        switch (httpMethod) {
            case 'OPTIONS':
                return {
                    statusCode: 200,
                    headers,
                    body: ''
                };
                
            case 'GET':
                if (pathParameters?.proposalId) {
                    return await getProposal(pathParameters.proposalId, headers);
                } else {
                    return await getProposals(queryStringParameters || {}, headers);
                }
                
            case 'POST':
                return await createProposal(JSON.parse(body || '{}'), headers);
                
            case 'PUT':
                if (pathParameters?.proposalId) {
                    return await updateProposal(pathParameters.proposalId, JSON.parse(body || '{}'), headers);
                }
                throw new Error('Proposal ID required for PUT operation');
                
            case 'DELETE':
                if (pathParameters?.proposalId) {
                    return await deleteProposal(pathParameters.proposalId, headers);
                }
                throw new Error('Proposal ID required for DELETE operation');
                
            default:
                throw new Error(`Unsupported method: ${httpMethod}`);
        }
    } catch (error) {
        console.error('Error:', error);
        return {
            statusCode: error.statusCode || 500,
            headers,
            body: JSON.stringify({
                error: error.message || 'Internal server error'
            })
        };
    }
};

// Get single proposal
async function getProposal(proposalId, headers) {
    console.log('Getting proposal:', proposalId);
    
    const params = {
        TableName: PROPOSALS_TABLE,
        KeyConditionExpression: 'proposalId = :proposalId',
        ExpressionAttributeValues: {
            ':proposalId': proposalId
        },
        ScanIndexForward: false, // Get latest version first
        Limit: 1
    };
    
    const result = await dynamodb.query(params).promise();
    
    if (result.Items.length === 0) {
        return {
            statusCode: 404,
            headers,
            body: JSON.stringify({ error: 'Proposal not found' })
        };
    }
    
    return {
        statusCode: 200,
        headers,
        body: JSON.stringify(result.Items[0])
    };
}

// Get all proposals with optional filtering
async function getProposals(queryParams, headers) {
    console.log('Getting proposals with filters:', queryParams);
    
    const { status, agency, assignedTo, limit = 50 } = queryParams;
    
    let params;
    
    if (status) {
        // Use status-lastModified-index for status filtering
        params = {
            TableName: PROPOSALS_TABLE,
            IndexName: 'status-lastModified-index',
            KeyConditionExpression: '#status = :status',
            ExpressionAttributeNames: {
                '#status': 'status'
            },
            ExpressionAttributeValues: {
                ':status': status
            },
            ScanIndexForward: false, // Most recent first
            Limit: parseInt(limit)
        };
    } else if (agency) {
        // Use agency-deadline-index for agency filtering
        params = {
            TableName: PROPOSALS_TABLE,
            IndexName: 'agency-deadline-index',
            KeyConditionExpression: 'agency = :agency',
            ExpressionAttributeValues: {
                ':agency': agency
            },
            ScanIndexForward: true, // Earliest deadline first
            Limit: parseInt(limit)
        };
    } else if (assignedTo) {
        // Use assignedTo-lastModified-index for team member filtering
        params = {
            TableName: PROPOSALS_TABLE,
            IndexName: 'assignedTo-lastModified-index',
            KeyConditionExpression: 'assignedTo = :assignedTo',
            ExpressionAttributeValues: {
                ':assignedTo': assignedTo
            },
            ScanIndexForward: false, // Most recent first
            Limit: parseInt(limit)
        };
    } else {
        // Scan all proposals (use sparingly)
        params = {
            TableName: PROPOSALS_TABLE,
            Limit: parseInt(limit)
        };
    }
    
    const result = status || agency || assignedTo 
        ? await dynamodb.query(params).promise()
        : await dynamodb.scan(params).promise();
    
    return {
        statusCode: 200,
        headers,
        body: JSON.stringify({
            proposals: result.Items,
            count: result.Count,
            scannedCount: result.ScannedCount
        })
    };
}

// Create new proposal
async function createProposal(proposalData, headers) {
    console.log('Creating proposal:', proposalData.title);
    
    const now = new Date().toISOString();
    const proposalId = proposalData.id || `proposal-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
    
    const proposal = {
        proposalId,
        lastModified: now,
        createdAt: now,
        version: 1,
        ...proposalData,
        // Searchable text for future full-text search
        searchableText: [
            proposalData.title,
            proposalData.agency,
            proposalData.executiveSummary,
            proposalData.technicalApproach,
            proposalData.assignedTo
        ].filter(Boolean).join(' ').toLowerCase()
    };
    
    const params = {
        TableName: PROPOSALS_TABLE,
        Item: proposal,
        ConditionExpression: 'attribute_not_exists(proposalId)'
    };
    
    try {
        await dynamodb.put(params).promise();
        
        return {
            statusCode: 201,
            headers,
            body: JSON.stringify(proposal)
        };
    } catch (error) {
        if (error.code === 'ConditionalCheckFailedException') {
            return {
                statusCode: 409,
                headers,
                body: JSON.stringify({ error: 'Proposal already exists' })
            };
        }
        throw error;
    }
}

// Update existing proposal
async function updateProposal(proposalId, proposalData, headers) {
    console.log('Updating proposal:', proposalId);
    
    // Get current version first
    const getCurrentParams = {
        TableName: PROPOSALS_TABLE,
        KeyConditionExpression: 'proposalId = :proposalId',
        ExpressionAttributeValues: {
            ':proposalId': proposalId
        },
        ScanIndexForward: false,
        Limit: 1
    };
    
    const currentResult = await dynamodb.query(getCurrentParams).promise();
    
    if (currentResult.Items.length === 0) {
        return {
            statusCode: 404,
            headers,
            body: JSON.stringify({ error: 'Proposal not found' })
        };
    }
    
    const currentProposal = currentResult.Items[0];
    const now = new Date().toISOString();
    
    const updatedProposal = {
        ...currentProposal,
        ...proposalData,
        proposalId,
        lastModified: now,
        version: (currentProposal.version || 1) + 1,
        // Update searchable text
        searchableText: [
            proposalData.title || currentProposal.title,
            proposalData.agency || currentProposal.agency,
            proposalData.executiveSummary || currentProposal.executiveSummary,
            proposalData.technicalApproach || currentProposal.technicalApproach,
            proposalData.assignedTo || currentProposal.assignedTo
        ].filter(Boolean).join(' ').toLowerCase()
    };
    
    const params = {
        TableName: PROPOSALS_TABLE,
        Item: updatedProposal
    };
    
    await dynamodb.put(params).promise();
    
    return {
        statusCode: 200,
        headers,
        body: JSON.stringify(updatedProposal)
    };
}

// Delete proposal
async function deleteProposal(proposalId, headers) {
    console.log('Deleting proposal:', proposalId);
    
    // Get all versions of the proposal first
    const getParams = {
        TableName: PROPOSALS_TABLE,
        KeyConditionExpression: 'proposalId = :proposalId',
        ExpressionAttributeValues: {
            ':proposalId': proposalId
        }
    };
    
    const result = await dynamodb.query(getParams).promise();
    
    if (result.Items.length === 0) {
        return {
            statusCode: 404,
            headers,
            body: JSON.stringify({ error: 'Proposal not found' })
        };
    }
    
    // Delete all versions
    const deletePromises = result.Items.map(item => {
        return dynamodb.delete({
            TableName: PROPOSALS_TABLE,
            Key: {
                proposalId: item.proposalId,
                lastModified: item.lastModified
            }
        }).promise();
    });
    
    await Promise.all(deletePromises);
    
    return {
        statusCode: 200,
        headers,
        body: JSON.stringify({ message: 'Proposal deleted successfully' })
    };
}